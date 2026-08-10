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
except ImportError:  # pragma: no cover - exercised when boto3 is absent
    boto3 = None

API_URL = "https://be-prod.track360.net.in/rest/integrations/generate-public-live-streaming-urls"
API_KEY = "YRMsHMOMDgDDJ3L1D14Qg2id5dkMYMrh"
DEFAULT_IMEI = "670078167679"
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PREFIX = os.getenv("S3_PREFIX", "videos")
DB_PATH = os.getenv("CLIP_DB_PATH", str(Path(__file__).with_name("clip_downloads.db")))


def initialize_database(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clip_downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT NOT NULL,
            date_str TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            status TEXT NOT NULL,
            file_path TEXT,
            s3_url TEXT,
            error TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def log_download_event(
    db_path: str,
    imei: str,
    date_str: str,
    start_time: str,
    end_time: str,
    status: str,
    file_path: str | None = None,
    s3_url: str | None = None,
    error: str = "",
):
    conn = initialize_database(db_path)
    conn.execute(
        """
        INSERT INTO clip_downloads (
            imei, date_str, start_time, end_time, status, file_path, s3_url, error, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            imei,
            date_str,
            start_time,
            end_time,
            status,
            file_path,
            s3_url,
            error,
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
        ),
    )
    conn.commit()
    conn.close()


def upload_to_s3(file_path: str, imei: str, date_str: str, start_time: str, end_time: str):
    if not S3_BUCKET:
        return None

    if boto3 is None:
        raise RuntimeError("boto3 is required for S3 uploads. Install it with: pip install boto3")

    key = f"{S3_PREFIX}/{imei}/{date_str}/{Path(file_path).stem}-{start_time.replace(':', '')}-{end_time.replace(':', '')}.mp4"
    s3_client = boto3.client("s3")
    s3_client.upload_file(file_path, S3_BUCKET, key)
    return f"https://{S3_BUCKET}.s3.amazonaws.com/{key}"


def parse_hms(value: str) -> datetime:
    return datetime.strptime(value, "%H:%M:%S")


def format_hms(value: datetime) -> str:
    return value.strftime("%H:%M:%S")


def load_scheduler_state(state_file: str, imei: str, date_str: str):
    if not state_file or not os.path.exists(state_file):
        return None

    try:
        with open(state_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None

    if data.get("imei") != imei or data.get("date") != date_str:
        return None

    return data


def save_scheduler_state(state_file: str, imei: str, date_str: str, last_processed_end_time: str):
    if not state_file:
        return

    payload = {
        "imei": imei,
        "date": date_str,
        "last_processed_end_time": last_processed_end_time,
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

    with open(state_file, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def resolve_next_interval(date_str: str, start_time: str, end_time: str, state_file: str, imei: str):
    state = load_scheduler_state(state_file, imei, date_str)
    if state and state.get("last_processed_end_time"):
        next_start = state["last_processed_end_time"]
        next_end = format_hms(parse_hms(next_start) + timedelta(minutes=1))
        print(f"Resuming from scheduler checkpoint: {next_start} -> {next_end}")
        return next_start, next_end

    return start_time, end_time


def iter_intervals(date_str: str, start_time: str, end_time: str, state_file: str, imei: str):
    state = load_scheduler_state(state_file, imei, date_str)
    current_start_dt = parse_hms(start_time)
    if state and state.get("last_processed_end_time"):
        current_start_dt = parse_hms(state["last_processed_end_time"])

    target_end_dt = parse_hms(end_time)
    while current_start_dt < target_end_dt:
        next_end_dt = min(current_start_dt + timedelta(minutes=1), target_end_dt)
        yield format_hms(current_start_dt), format_hms(next_end_dt)
        current_start_dt = next_end_dt


def fetch_playback_url(imei: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    payload = {
        "imei": imei,
        "validityMinutes": 60
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    url = data["data"]["GeneratePublicLiveStreamingUrls"]["historyPlaybackUrl"]
    print(f"Got playback URL: {url}")
    return url


def download_video_clip(
    playback_url: str,
    date_str: str,
    start_time: str,
    end_time: str,
    output_dir: str,
    state_file: str | None = None,
    imei: str = DEFAULT_IMEI,
):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print(f"Opening: {playback_url}")
        page.goto(playback_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # ── Step 1: Click "Download History" tab ──────────────────────────────
        print("Clicking Download History tab...")
        page.click("text=Download History")
        page.wait_for_timeout(1500)

        # ── Steps 2-4: Fill Date, Start Time, End Time using exact IDs from DOM ──
        # Confirmed IDs from DOM inspection:
        #   Date field  → #history_start_time        (type=text, placeholder="Select Date")
        #   Start Time  → #history_start_time_input  (type=time)
        #   End Time    → #history_end_time_input     (type=time)
        # Date value format: MM/DD/YYYY  e.g. "08/06/2026"
        print(f"Setting Date: {date_str} | Start: {start_time} | End: {end_time}")

        # Exact IDs confirmed from DOM dump:
        #   Date input  → id="history_start_time"        type=text  (confusingly named, it's the date field)
        #   Start Time  → id="history_start_time_input"  type=time
        #   End Time    → id="history_end_time_input"    type=time
        # Date string format used by this page: MM/DD/YYYY (e.g. "08/06/2026")

        result = page.evaluate("""
            ([dateVal, startVal, endVal]) => {
                const log = [];

                function setField(el, val, label) {
                    if (!el) { log.push(label + ': NOT FOUND'); return; }
                    el.removeAttribute("disabled");
                    el.removeAttribute("readonly");
                    el.value = val;
                    el.dispatchEvent(new Event('input',  { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    log.push(label + ' -> "' + el.value + '"  [id=' + el.id + ' type=' + el.type + ']');
                }

                // Date field (text input that shows the date)
                setField(document.getElementById('history_start_time'),       dateVal,  'Date');

                // Start Time (time input)
                setField(document.getElementById('history_start_time_input'), startVal, 'StartTime');

                // End Time (time input)
                setField(document.getElementById('history_end_time_input'),   endVal,   'EndTime');

                return log;
            }
        """, [date_str, start_time, end_time])

        print("  [FILL RESULT]")
        for line in result:
            print(f"    {line}")

        page.wait_for_timeout(600)

        # ── Step 5: Screenshot before clicking to debug ──────────────────────────
        page.screenshot(path="before_download_click.png")
        print("Screenshot saved: before_download_click.png")

        # ── Step 5: Dump all buttons on page to find the right one ────────────
        buttons_info = page.evaluate("""
            () => Array.from(document.querySelectorAll('button, [role=button]')).map((el, i) => ({
                index: i,
                text: el.textContent.trim().substring(0, 80),
                id: el.id,
                className: el.className.substring(0, 80),
                visible: el.offsetParent !== null
            }))
        """)
        print("  [BUTTONS ON PAGE]")
        for b in buttons_info:
            print(f"    [{b['index']}] visible={b['visible']} id='{b['id']}' text='{b['text']}' class='{b['className']}'")

        # ── Step 5: Click the green Download button inside the Download History section ──
        print("Clicking Download button...")
        try:
            page.wait_for_selector("#history_btn_download", timeout=10000)
            page.click("#history_btn_download")
            print("  Clicked #history_btn_download")
        except Exception:
            page.screenshot(path="timeout_debug.png")
            raise RuntimeError("Could not click the history_btn_download button. Check timeout_debug.png screenshot.")
        page.wait_for_timeout(2000)

        # Screenshot after clicking
        page.screenshot(path="after_download_click.png")
        print("Screenshot saved: after_download_click.png")

        # ── Step 6: Wait for the History Playback popup to appear ─────────────
        print("Waiting for the History Playback popup...")
        try:
            page.wait_for_selector("text=History Playback", timeout=30000)
            print("  ✓ History Playback popup appeared")
        except Exception:
            page.screenshot(path="timeout_debug.png")
            raise RuntimeError("History Playback popup never appeared. Check timeout_debug.png screenshot.")

        page.wait_for_timeout(1000)

        # ── Step 7: Click the exact green popup download button ───────────────
        print("Clicking exact popup download button...")
        base_name = (
            f"video_{date_str.replace(' ', '_')}"
            f"_{start_time.replace(':', '')}"
            f"-{end_time.replace(':', '')}"
        )

        download_button_selector = "button:has(img[src*='icon-download-video.png'])"
        try:
            page.wait_for_selector(download_button_selector, state="visible", timeout=30000)
            print(f"  ✓ Found popup download button: {download_button_selector}")
        except Exception:
            page.screenshot(path="timeout_debug.png")
            raise RuntimeError("Popup download button was not found. Check timeout_debug.png screenshot.")

        download_candidates = []
        download_response = None

        def handle_download(download):
            download_candidates.append(download)

        def handle_response(response):
            nonlocal download_response
            if download_response is not None:
                return
            url = response.url.lower()
            content_type = (response.headers.get("content-type") or "").lower()
            content_disposition = (response.headers.get("content-disposition") or "").lower()
            if (
                ".mp4" in url or ".flv" in url or ".mp3" in url or 
                "video" in content_type or "octet-stream" in content_type or
                "attachment" in content_disposition
            ):
                download_response = response

        page.on("download", handle_download)
        page.on("response", handle_response)

        page.click(download_button_selector)
        page.wait_for_timeout(5000)

        if download_candidates:
            download = download_candidates[0]
            save_path = os.path.join(output_dir, f"{base_name}.mp4")
            download.save_as(save_path)
            print(f"\n✅ Video saved to: {save_path}")
        elif download_response is not None:
            save_path = os.path.join(output_dir, f"{base_name}.mp4")
            body = download_response.body()
            with open(save_path, "wb") as fh:
                fh.write(body)
            print(f"\n✅ Video saved from response to: {save_path}")
        else:
            page.screenshot(path="timeout_debug.png")
            raise RuntimeError("No download was triggered by the popup button.")

        s3_url = upload_to_s3(save_path, imei, date_str, start_time, end_time)
        if s3_url:
            print(f"Uploaded to S3: {s3_url}")
        else:
            print("S3 upload skipped because S3_BUCKET is not set")

        log_download_event(
            DB_PATH,
            imei,
            date_str,
            start_time,
            end_time,
            "success",
            save_path,
            s3_url,
            "",
        )

        os.remove(save_path)
        print(f"Removed local temp file: {save_path}")

        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Automate Track360 Video History Download",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  python download_video.py --date "2026-08-06" --start "01:01:01" --end "01:02:00"
  python download_video.py --date "2026-08-07" --start "10:30:00" --end "10:31:00" --imei "670078167679"
        """
    )
    parser.add_argument("--date",  required=True,  help="Date in YYYY-MM-DD format, e.g. '2026-08-06'")
    parser.add_argument("--start", required=True,  help="Start time HH:MM:SS, e.g. '01:01:01'")
    parser.add_argument("--end",   required=True,  help="End time HH:MM:SS,   e.g. '01:02:00'")
    parser.add_argument("--imei",  default=DEFAULT_IMEI, help="Device IMEI (default: 670078167679)")
    parser.add_argument("--state-file", default=str(Path(__file__).with_name(".scheduler_state.json")), help="Path to the checkpoint JSON file")
    parser.add_argument("--reset-state", action="store_true", help="Reset the scheduler checkpoint before running")

    args = parser.parse_args()

    # Convert YYYY-MM-DD  →  MM/DD/YYYY  (format the page expects)
    from datetime import datetime
    try:
        date_obj = datetime.strptime(args.date, "%Y-%m-%d")
        date_for_page = date_obj.strftime("%m/%d/%Y")   # e.g. "08/06/2026"
    except ValueError:
        print("ERROR: --date must be in YYYY-MM-DD format, e.g. 2026-08-06")
        exit(1)

    downloads_folder = str(Path.home() / "Downloads")
    os.makedirs(downloads_folder, exist_ok=True)

    if args.reset_state and os.path.exists(args.state_file):
        os.remove(args.state_file)
        print(f"Reset scheduler state at {args.state_file}")

    start_time, end_time = resolve_next_interval(args.date, args.start, args.end, args.state_file, args.imei)
    print(f"Using initial interval: {start_time} -> {end_time}")

    print(f"\n{'='*55}")
    print(f"  IMEI      : {args.imei}")
    print(f"  Date      : {args.date}  →  {date_for_page} (page format)")
    print(f"  Start     : {args.start}")
    print(f"  End       : {args.end}")
    print(f"  Save to   : {downloads_folder}")
    print(f"{'='*55}\n")

    for index, (interval_start, interval_end) in enumerate(
        iter_intervals(args.date, start_time, args.end, args.state_file, args.imei),
        start=1,
    ):
        print(f"\n[{index}] Processing interval: {interval_start} -> {interval_end}")
        try:
            playback_url = fetch_playback_url(args.imei)
            download_video_clip(
                playback_url,
                date_for_page,
                interval_start,
                interval_end,
                downloads_folder,
                state_file=args.state_file,
                imei=args.imei,
            )
        except Exception as exc:
            print(f"Failed interval {interval_start} -> {interval_end}: {exc}")
            log_download_event(
                DB_PATH,
                args.imei,
                args.date,
                interval_start,
                interval_end,
                "failed",
                None,
                None,
                str(exc),
            )
            continue
