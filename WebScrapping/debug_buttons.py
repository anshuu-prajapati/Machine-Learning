import requests
from playwright.sync_api import sync_playwright

API_URL = "https://be-prod.track360.net.in/rest/integrations/generate-public-live-streaming-urls"
API_KEY = "YRMsHMOMDgDDJ3L1D14Qg2id5dkMYMrh"
DEFAULT_IMEI = "670078167679"

def fetch_playback_url(imei):
    headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}
    payload = {"imei": imei, "validityMinutes": 60}
    r = requests.post(API_URL, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["data"]["GeneratePublicLiveStreamingUrls"]["historyPlaybackUrl"]

url = fetch_playback_url(DEFAULT_IMEI)
print(f"URL: {url}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    page.click("text=Download History")
    page.wait_for_timeout(1500)

    # ── PHASE 1: Buttons BEFORE clicking Download ─────────────────────────
    print(f"\n{'='*60}")
    print("PHASE 1 — BUTTONS BEFORE clicking Download:")
    print(f"{'='*60}")
    buttons_before = page.evaluate("""
        () => Array.from(document.querySelectorAll('button')).map((el, i) => ({
            index: i,
            id: el.id,
            text: el.textContent.trim().substring(0, 60),
            className: el.className.substring(0, 120),
            visible: el.offsetParent !== null,
            outerHTML: el.outerHTML.substring(0, 250)
        }))
    """)
    for b in buttons_before:
        print(f"[{b['index']}] visible={b['visible']} id='{b['id']}' text='{b['text']}'")
        print(f"       html={b['outerHTML']}\n")

    # ── Fill form ─────────────────────────────────────────────────────────
    page.click("#trigger_download_history")
    page.wait_for_timeout(800)
    page.evaluate("""
        () => {
            const dayBtns = Array.from(document.querySelectorAll('button.pika-button.pika-day'));
            const btn = dayBtns.find(b => b.textContent.trim() === '6');
            if (btn) btn.click();
            else console.error('day 6 not found');
        }
    """)
    page.wait_for_timeout(800)
    page.evaluate("""
        () => {
            function set(id, val) {
                const el = document.getElementById(id);
                if (!el) { console.error('NOT FOUND: ' + id); return; }
                el.removeAttribute('disabled');
                el.value = val;
                el.dispatchEvent(new Event('input',  { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
            set('history_start_time_input', '01:01:01');
            set('history_end_time_input',   '01:02:00');
        }
    """)
    page.wait_for_timeout(500)

    # ── Click Download button ─────────────────────────────────────────────
    print("Clicking #history_btn_download ...")
    page.click("#history_btn_download")
    page.wait_for_timeout(5000)  # wait for results to load

    # ── PHASE 2: Buttons AFTER clicking Download ──────────────────────────
    print(f"\n{'='*60}")
    print("PHASE 2 — VISIBLE BUTTONS AFTER clicking Download:")
    print(f"{'='*60}")
    buttons_after = page.evaluate("""
        () => Array.from(document.querySelectorAll('button')).map((el, i) => ({
            index: i,
            id: el.id,
            text: el.textContent.trim().substring(0, 60),
            className: el.className.substring(0, 120),
            visible: el.offsetParent !== null,
            bgColor: window.getComputedStyle(el).backgroundColor,
            outerHTML: el.outerHTML.substring(0, 300)
        }))
    """)
    for b in buttons_after:
        if b['visible']:
            print(f"[{b['index']}] id='{b['id']}' text='{b['text']}' bg='{b['bgColor']}'")
            print(f"       class='{b['className']}'")
            print(f"       html={b['outerHTML']}\n")

    # ── Page text snippet ─────────────────────────────────────────────────
    page_text = page.evaluate("() => document.body.innerText")
    print(f"\n{'='*60}")
    print("PAGE TEXT (first 800 chars):")
    print(f"{'='*60}")
    print(page_text[:800])

    browser.close()