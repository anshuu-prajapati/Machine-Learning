import requests
from playwright.sync_api import sync_playwright

API_URL = "https://be-prod.track360.net.in/rest/integrations/generate-public-live-streaming-urls"
API_KEY = "YRMsHMOMDgDDJ3L1D14Qg2id5dkMYMrh"
DEFAULT_IMEI = "670078167679"

def fetch_playback_url(imei: str) -> str:
    headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}
    payload = {"imei": imei, "validityMinutes": 60}
    response = requests.post(API_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["data"]["GeneratePublicLiveStreamingUrls"]["historyPlaybackUrl"]

url = fetch_playback_url(DEFAULT_IMEI)
print(f"URL: {url}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # Click Download History tab
    page.click("text=Download History")
    page.wait_for_timeout(1500)

    # Dump ALL inputs
    inputs = page.evaluate("""
        () => Array.from(document.querySelectorAll('input')).map((el, i) => ({
            index: i,
            id: el.id,
            name: el.name,
            type: el.type,
            placeholder: el.placeholder,
            value: el.value,
            className: el.className,
            outerHTML: el.outerHTML.substring(0, 200)
        }))
    """)

    print(f"\n{'='*60}")
    print(f"TOTAL INPUTS FOUND: {len(inputs)}")
    print(f"{'='*60}")
    for inp in inputs:
        print(f"\n[{inp['index']}]")
        print(f"  type        : {inp['type']}")
        print(f"  id          : {inp['id']}")
        print(f"  name        : {inp['name']}")
        print(f"  placeholder : {inp['placeholder']}")
        print(f"  value       : {inp['value']}")
        print(f"  class       : {inp['className']}")
        print(f"  outerHTML   : {inp['outerHTML']}")

    # Also dump labels
    labels = page.evaluate("""
        () => Array.from(document.querySelectorAll('label')).map(l => ({
            for: l.htmlFor,
            text: l.textContent.trim(),
            outerHTML: l.outerHTML.substring(0, 200)
        }))
    """)
    print(f"\n{'='*60}")
    print(f"LABELS FOUND: {len(labels)}")
    print(f"{'='*60}")
    for lbl in labels:
        print(f"  for='{lbl['for']}' text='{lbl['text']}' html={lbl['outerHTML']}")

    browser.close()