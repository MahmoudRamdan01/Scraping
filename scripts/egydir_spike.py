"""Spike: evaluate scraping EgyDir (a JS/AJAX SPA) with Playwright.

EgyDir serves the same 16 KB homepage for every path and exposes no public data
endpoint, so `requests` can't get listings. This spike checks whether a real
browser (Playwright) renders the listings so we can decide if a stable
Playwright-based scraper is worth building.

Run:
  pip install playwright && playwright install chromium
  python scripts/egydir_spike.py
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

CANDIDATE_URLS = [
    "https://www.egydir.com/ar",
    "https://www.egydir.com/ar/companies",
    "https://www.egydir.com/ar/factory",
]


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    insecure = str(os.environ.get("AOL_INSECURE_SSL", "false")).lower() in {"1", "true", "yes", "on"}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                ignore_https_errors=insecure,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
            )
            page = context.new_page()
            for url in CANDIDATE_URLS:
                try:
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2500)
                    html = page.content()
                    links = page.eval_on_selector_all(
                        "a",
                        "els => els.map(e => e.getAttribute('href'))"
                        ".filter(h => h && (h.includes('company') || h.includes('/ar/')))",
                    )
                    print(f"{url} -> rendered {len(html)} bytes, {len(links)} candidate links")
                    if links:
                        print("   sample:", links[:8])
                except Exception as exc:  # noqa: BLE001
                    print(f"{url} -> ERROR {type(exc).__name__}: {str(exc)[:120]}")
            browser.close()
    except Exception as exc:  # noqa: BLE001
        print("Playwright launch failed (browser not installed?):", type(exc).__name__, str(exc)[:160])
        print("Verdict: run on a machine where `playwright install chromium` succeeds.")


if __name__ == "__main__":
    main()
