import argparse
import os
import time
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright

API_URL = "https://be-prod.track360.net.in/rest/integrations/generate-public-live-streaming-urls"
API_KEY = "YRMsHMOMDgDDJ3L1D14Qg2id5dkMYMrh"
DEFAULT_IMEI = "670078167679"


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


def download_video_clip(playback_url: str, date_str: str, start_time: str, end_time: str, output_dir: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Set True once confirmed working
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

        with page.expect_download(timeout=120000) as download_info:
            page.click(download_button_selector)

        download = download_info.value
        save_path = os.path.join(output_dir, f"{base_name}.mp4")
        download.save_as(save_path)
        print(f"\n✅ Video saved to: {save_path}")

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

    print(f"\n{'='*55}")
    print(f"  IMEI      : {args.imei}")
    print(f"  Date      : {args.date}  →  {date_for_page} (page format)")
    print(f"  Start     : {args.start}")
    print(f"  End       : {args.end}")
    print(f"  Save to   : {downloads_folder}")
    print(f"{'='*55}\n")

    url = fetch_playback_url(args.imei)
    download_video_clip(url, date_for_page, args.start, args.end, downloads_folder)
