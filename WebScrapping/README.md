# WebScrapping

This folder contains Playwright-based automation for downloading video history from the Track360 streaming portal.

## Files

- `download_video.py`: main script to fetch a playback URL, open the Track360 page, select Download History, fill the date/time range, and click through to download the file.
- `debug_buttons.py`: helper script used to inspect page buttons and troubleshoot click selectors during development.
- `fixed.py`: an alternate copy of the script with additional fixes applied during debugging.
- `venv/`: Python virtual environment for this folder.

## Setup

1. Open PowerShell in `WebScrapping`.
2. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
3. Make sure required packages are installed inside `venv`.
   ```powershell
   pip install -r requirements.txt
   ```

If `requirements.txt` is missing, install at least:
```powershell
pip install playwright requests
``` 
Then install Playwright browsers:
```powershell
playwright install

playwright install chromium
```

## Usage

Run the main downloader with date, start, and end times:

```powershell
python .\download_video.py --date "2026-08-06" --start "01:01:01" --end "01:02:00"
```

## Notes

- The script uses a Track360 API key to request a public playback URL.
- It is designed to automate the browser page for the `Download History` workflow.
- Screenshots are saved as `before_download_click.png`, `after_download_click.png`, and `timeout_debug.png` for debugging.

## Troubleshooting

- If the final download does not start, inspect `timeout_debug.png`.
- Check the active selectors in `debug_buttons.py`.
- Ensure the browser can run in `headless=False` mode for debugging.
