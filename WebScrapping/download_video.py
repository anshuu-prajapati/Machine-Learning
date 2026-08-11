import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

try:
    import boto3
except ImportError:
    boto3 = None

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
API_URL      = "https://be-prod.track360.net.in/rest/integrations/generate-public-live-streaming-urls"
API_KEY      = os.getenv("TRACK360_API_KEY",  "YRMsHMOMDgDDJ3L1D14Qg2id5dkMYMrh")
DEFAULT_IMEI = os.getenv("DEVICE_IMEI",       "670078167679")

S3_BUCKET    = os.getenv("S3_BUCKET",  "gtrac")
S3_PREFIX    = os.getenv("S3_PREFIX",  "videos")
S3_REGION    = os.getenv("S3_REGION",  "us-east-1")
S3_LOG_KEY   = os.getenv("S3_LOG_KEY", "logs/clip_downloads.db")
URL_EXPIRES  = int(os.getenv("URL_EXPIRES_SEC", "3600"))  # presigned URL TTL

DB_PATH      = os.getenv("CLIP_DB_PATH", str(Path(__file__).with_name("clip_downloads.db")))
OUTPUT_DIR   = os.getenv("OUTPUT_DIR",   str(Path.home() / "Downloads" / "track360_clips"))

OP_START_HOUR = 6    # 06:00 IST
OP_END_HOUR   = 22   # 22:00 IST
LAG_MINUTES   = 2    # request video this many minutes behind real-time


# ══════════════════════════════════════════════════════════════════════════════
#  TIME HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def now_ist() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def is_operating_hours() -> bool:
    return OP_START_HOUR <= now_ist().hour < OP_END_HOUR


def current_window() -> tuple[str, str, str, str]:
    now      = now_ist()
    end_dt   = now.replace(second=0, microsecond=0) - timedelta(minutes=LAG_MINUTES)
    start_dt = end_dt - timedelta(minutes=1)
    return (
        start_dt.strftime("%Y-%m-%d"),   # "2026-08-11"
        start_dt.strftime("%m/%d/%Y"),   # "08/11/2026"  ← page format
        start_dt.strftime("%H:%M:%S"),
        end_dt.strftime("%H:%M:%S"),
    )


def seconds_until_next_minute() -> float:
    now = datetime.utcnow()
    return 60 - now.second - now.microsecond / 1_000_000


def seconds_until_op_start() -> float:
    ist = now_ist()
    wake = (ist + timedelta(days=1)).replace(
        hour=OP_START_HOUR, minute=0, second=0, microsecond=0
    )
    return (wake - ist).total_seconds()


# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════════════════════
def initialize_database():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clip_downloads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            imei        TEXT NOT NULL,
            date_str    TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            status      TEXT NOT NULL,
            s3_key      TEXT,
            s3_url      TEXT,
            preview_url TEXT,
            error       TEXT,
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def log_event(imei, date_str, start_time, end_time, status,
              s3_key=None, s3_url=None, preview_url=None, error=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO clip_downloads
            (imei, date_str, start_time, end_time, status, s3_key, s3_url, preview_url, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (imei, date_str, start_time, end_time, status,
          s3_key, s3_url, preview_url, error,
          datetime.utcnow().isoformat(timespec="seconds") + "Z"))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  S3
# ══════════════════════════════════════════════════════════════════════════════
def get_s3():
    if boto3 is None:
        raise RuntimeError("boto3 not installed — run: pip install boto3")
    return boto3.client("s3", region_name=S3_REGION)


def upload_video(file_path: str, imei: str, date_str: str, start: str, end: str) -> tuple[str, str]:
    """Upload file to S3. Returns (s3_key, s3_url)."""
    key = (
        f"{S3_PREFIX}/{imei}/{date_str}/"
        f"clip_{start.replace(':', '')}-{end.replace(':', '')}.mp4"
    )
    get_s3().upload_file(file_path, S3_BUCKET, key)
    return key, f"s3://{S3_BUCKET}/{key}"


def generate_presigned_url(s3_key: str) -> str:
    """Generate a public-readable presigned URL valid for URL_EXPIRES seconds."""
    return get_s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": s3_key},
        ExpiresIn=URL_EXPIRES,
    )


def backup_db():
    if not os.path.exists(DB_PATH):
        return
    try:
        get_s3().upload_file(DB_PATH, S3_BUCKET, S3_LOG_KEY)
    except Exception as e:
        print(f"  [WARN] DB backup failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  TRACK360 API
# ══════════════════════════════════════════════════════════════════════════════
def fetch_playback_url(imei: str) -> str:
    resp = requests.post(
        API_URL,
        headers={"Content-Type": "application/json", "X-API-KEY": API_KEY},
        json={"imei": imei, "validityMinutes": 60},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"]["GeneratePublicLiveStreamingUrls"]["historyPlaybackUrl"]


# ══════════════════════════════════════════════════════════════════════════════
#  PLAYWRIGHT DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════
def download_clip(playback_url: str, date_page: str, start: str, end: str) -> str:
    """Returns local file path of downloaded clip."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx  = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        page.goto(playback_url, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2000)

        page.click("text=Download History")
        page.wait_for_timeout(1500)

        result = page.evaluate("""
            ([dateVal, startVal, endVal]) => {
                const log = [];
                function set(el, val, label) {
                    if (!el) { log.push(label + ': NOT FOUND'); return; }
                    el.removeAttribute('disabled');
                    el.removeAttribute('readonly');
                    el.value = val;
                    el.dispatchEvent(new Event('input',  { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    log.push(label + ' = "' + el.value + '"');
                }
                set(document.getElementById('history_start_time'),       dateVal,  'Date');
                set(document.getElementById('history_start_time_input'), startVal, 'Start');
                set(document.getElementById('history_end_time_input'),   endVal,   'End');
                return log;
            }
        """, [date_page, start, end])
        for line in result:
            print(f"    {line}")

        page.wait_for_timeout(600)

        try:
            page.wait_for_selector("#history_btn_download", timeout=10_000)
            page.click("#history_btn_download")
        except Exception:
            page.screenshot(path=str(Path(OUTPUT_DIR) / "debug_download_btn.png"))
            raise RuntimeError("Could not click #history_btn_download")

        page.wait_for_timeout(2000)

        try:
            page.wait_for_selector("text=History Playback", timeout=30_000)
        except Exception:
            page.screenshot(path=str(Path(OUTPUT_DIR) / "debug_popup.png"))
            raise RuntimeError("History Playback popup never appeared")

        page.wait_for_timeout(1000)

        dl_sel = "button:has(img[src*='icon-download-video.png'])"
        try:
            page.wait_for_selector(dl_sel, state="visible", timeout=30_000)
        except Exception:
            page.screenshot(path=str(Path(OUTPUT_DIR) / "debug_popup_btn.png"))
            raise RuntimeError("Popup download button not found")

        dl_list = []
        dl_resp  = None

        def on_download(d):   dl_list.append(d)
        def on_response(r):
            nonlocal dl_resp
            if dl_resp: return
            url = r.url.lower()
            ct  = (r.headers.get("content-type") or "").lower()
            cd  = (r.headers.get("content-disposition") or "").lower()
            if ".mp4" in url or ".flv" in url or "video" in ct or "octet-stream" in ct or "attachment" in cd:
                dl_resp = r

        page.on("download", on_download)
        page.on("response", on_response)
        page.click(dl_sel)
        page.wait_for_timeout(5000)

        fname     = f"clip_{date_page.replace('/', '-')}_{start.replace(':', '')}-{end.replace(':', '')}.mp4"
        save_path = str(Path(OUTPUT_DIR) / fname)

        if dl_list:
            dl_list[0].save_as(save_path)
        elif dl_resp:
            with open(save_path, "wb") as fh:
                fh.write(dl_resp.body())
        else:
            page.screenshot(path=str(Path(OUTPUT_DIR) / "debug_no_download.png"))
            raise RuntimeError("No download was triggered")

        browser.close()
        return save_path


# ══════════════════════════════════════════════════════════════════════════════
#  CORE: run one window end-to-end
# ══════════════════════════════════════════════════════════════════════════════
def run_window(imei: str, date_str: str, date_page: str, start_time: str, end_time: str):
    print(f"\n{'─'*60}")
    print(f"  [{now_ist().strftime('%Y-%m-%d %H:%M:%S')} IST]")
    print(f"  Window : {date_str}  {start_time} → {end_time}")
    print(f"{'─'*60}")

    try:
        print("  → Fetching playback URL...")
        url = fetch_playback_url(imei)

        print("  → Downloading clip via Playwright...")
        save_path = download_clip(url, date_page, start_time, end_time)
        print(f"  → Clip saved locally: {save_path}")

        print("  → Uploading to S3...")
        s3_key, s3_uri = upload_video(save_path, imei, date_str, start_time, end_time)
        print(f"  → S3 URI : {s3_uri}")

        print("  → Generating presigned preview URL...")
        preview_url = generate_presigned_url(s3_key)

        # ── Remove local temp file ────────────────────────────────────────────
        os.remove(save_path)

        # ── Log to DB ─────────────────────────────────────────────────────────
        log_event(imei, date_str, start_time, end_time, "success",
                  s3_key, s3_uri, preview_url)

        # ── Print preview URL prominently ─────────────────────────────────────
        ttl_min = URL_EXPIRES // 60
        print(f"\n  {'='*58}")
        print(f"  ✅  CLIP READY — open this URL in your browser:")
        print(f"  {'='*58}")
        print(f"\n  {preview_url}\n")
        print(f"  (link valid for {ttl_min} minutes)")
        print(f"  {'='*58}\n")

        return preview_url

    except Exception as exc:
        print(f"\n  ❌  Error: {exc}")
        log_event(imei, date_str, start_time, end_time, "failed", error=str(exc))
        return None

    finally:
        backup_db()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Track360 auto video downloader + S3 preview")
    parser.add_argument("--date",  help="YYYY-MM-DD  (manual one-shot mode)")
    parser.add_argument("--start", help="HH:MM:SS    (manual one-shot mode)")
    parser.add_argument("--end",   help="HH:MM:SS    (manual one-shot mode)")
    parser.add_argument("--imei",  default=os.getenv("DEVICE_IMEI", DEFAULT_IMEI))
    args = parser.parse_args()

    print("=" * 60)
    print("  Track360 Video Scraper")
    print(f"  IMEI    : {args.imei}")
    print(f"  Hours   : {OP_START_HOUR:02d}:00 – {OP_END_HOUR:02d}:00 IST")
    print(f"  Bucket  : s3://{S3_BUCKET}/{S3_PREFIX}/  [{S3_REGION}]")
    print(f"  DB      : {DB_PATH}")
    print(f"  URL TTL : {URL_EXPIRES // 60} min")
    print("=" * 60)

    initialize_database()

    # ── Manual one-shot ───────────────────────────────────────────────────────
    if args.date and args.start and args.end:
        print(f"\n  [MANUAL]  {args.date}  {args.start} → {args.end}")
        date_page = datetime.strptime(args.date, "%Y-%m-%d").strftime("%m/%d/%Y")
        run_window(args.imei, args.date, date_page, args.start, args.end)
        return

    # ── Auto-scheduler loop ───────────────────────────────────────────────────
    print("\n  [AUTO MODE]  Running every minute — Ctrl+C to stop\n")
    while True:
        if not is_operating_hours():
            secs   = seconds_until_op_start()
            wake   = (now_ist() + timedelta(seconds=secs)).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  💤  Outside {OP_START_HOUR:02d}:00–{OP_END_HOUR:02d}:00 IST. "
                  f"Sleeping {secs/3600:.1f} hrs until {wake} IST")
            time.sleep(secs)
            continue

        date_str, date_page, start_time, end_time = current_window()
        run_window(args.imei, date_str, date_page, start_time, end_time)

        secs = seconds_until_next_minute() + 2
        print(f"  ⏱  Next window in {secs:.0f}s...")
        time.sleep(secs)


if __name__ == "__main__":
    main()