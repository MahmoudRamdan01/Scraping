"""Google Maps scraper — the PRIMARY source for END CUSTOMERS.

Unlike the freight directories (which list shipping companies), Google Maps
returns the actual businesses the sales team sells to: manufacturers, importers,
exporters, factories, cosmetics/pharma/food/garment companies, etc. — searched
by business role + category + city, e.g. "Cosmetics Manufacturers in Cairo".

Verified against the live site (2026): a Playwright (real browser) opens the
search, scrolls the results feed to load more, then opens each place and reads
name / phone / website / address from the detail panel's ``data-item-id``
buttons. Phones are validated downstream by the pipeline.

This is the YELLOW tier: it needs Playwright + a browser installed and is
best-effort (Google updates its DOM and bot defenses). It fails gracefully —
a blocked or empty run yields nothing rather than crashing the whole search.
"""
from __future__ import annotations

import os
import re
from typing import Iterator, Optional

from ..base import BaseScraper, RawLead, SearchRequest

# Business roles -> the phrasing used in the Maps query.
ROLE_QUERY = {
    "Manufacturer": "manufacturers",
    "Factory": "factories",
    "Importer": "importers",
    "Exporter": "exporters",
    "Distributor": "distributors",
    "Wholesaler": "wholesalers",
    "Supplier": "suppliers",
}

_AL_PREFIX = re.compile(r"^(phone:|website:|address:|الهاتف:|العنوان:)\s*", re.I)


def _clean_label(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return _AL_PREFIX.sub("", value.strip()).strip() or None


def build_query(req: SearchRequest) -> str:
    """e.g. ('Cosmetics', 'Manufacturer', 'Cairo') -> 'Cosmetics manufacturers in Cairo Egypt'."""
    parts: list[str] = []
    if req.category:
        parts.append(req.category)
    role_word = ROLE_QUERY.get(req.role or "", (req.role or "").lower())
    if role_word:
        parts.append(role_word)
    if not parts:
        parts.append("companies")
    where = req.city or req.governorate or ""
    q = " ".join(parts)
    if where:
        q += f" in {where}"
    if req.country:
        q += f" {req.country}"
    return q.strip()


class GoogleMapsScraper(BaseScraper):
    key = "google_maps"
    label = "Google Maps (business listings)"
    tier = "yellow"

    # Conservative defaults (verified live). The autopilot can lower these via env
    # (AOL_MAPS_*) to trade a little recall for a lot of speed across many queries.
    SCROLL_ROUNDS = 8
    SCROLL_PAUSE_MS = 1600
    DETAIL_PAUSE_MS = 1500
    CONSENT_PAUSE_MS = 3500
    NAV_TIMEOUT_MS = 45000
    DETAIL_TIMEOUT_MS = 30000

    def __init__(self, meta: Optional[dict] = None):
        super().__init__(meta)

        def _i(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, default))
            except (TypeError, ValueError):
                return default

        self.scroll_rounds = _i("AOL_MAPS_SCROLL_ROUNDS", self.SCROLL_ROUNDS)
        self.scroll_pause_ms = _i("AOL_MAPS_SCROLL_PAUSE_MS", self.SCROLL_PAUSE_MS)
        self.detail_pause_ms = _i("AOL_MAPS_DETAIL_PAUSE_MS", self.DETAIL_PAUSE_MS)
        self.consent_pause_ms = _i("AOL_MAPS_CONSENT_PAUSE_MS", self.CONSENT_PAUSE_MS)
        self.nav_timeout_ms = _i("AOL_MAPS_NAV_TIMEOUT_MS", self.NAV_TIMEOUT_MS)
        self.detail_timeout_ms = _i("AOL_MAPS_DETAIL_TIMEOUT_MS", self.DETAIL_TIMEOUT_MS)

    def _insecure(self) -> bool:
        return str(os.environ.get("AOL_INSECURE_SSL", "false")).strip().lower() in {"1", "true", "yes", "on"}

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "Google Maps needs Playwright. Run: pip install playwright && playwright install chromium"
            ) from exc

        query = build_query(req)
        url = "https://www.google.com/maps/search/" + query.replace(" ", "+")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                ignore_https_errors=self._insecure(),
                locale="en-US",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
                page.wait_for_timeout(self.consent_pause_ms)
                self._dismiss_consent(page)
                place_urls = self._collect_place_urls(page, req.max_results)

                emitted = 0
                for place_url in place_urls:
                    lead = self._scrape_place(page, place_url, req)
                    if lead is not None:
                        yield lead
                        emitted += 1
                        if emitted >= req.max_results:
                            break
                    self.polite_sleep()
            finally:
                browser.close()

    def _dismiss_consent(self, page) -> None:
        for sel in (
            "button[aria-label*='Accept all']",
            "button[aria-label*='Reject all']",
            "form[action*='consent'] button",
        ):
            try:
                btn = page.query_selector(sel)
                if btn:
                    btn.click()
                    page.wait_for_timeout(1500)
                    return
            except Exception:  # noqa: BLE001
                continue

    def _collect_place_urls(self, page, want: int) -> list[str]:
        seen: list[str] = []
        for _ in range(self.scroll_rounds):
            for a in page.query_selector_all("a[href*='/maps/place/']"):
                href = a.get_attribute("href")
                if href and href not in seen:
                    seen.append(href)
            if len(seen) >= want:
                break
            try:
                page.eval_on_selector("div[role='feed']", "el => el.scrollTo(0, el.scrollHeight)")
            except Exception:  # noqa: BLE001 - feed not present yet
                pass
            page.wait_for_timeout(self.scroll_pause_ms)
        return seen[: max(want, 0)]

    def _scrape_place(self, page, place_url: str, req: SearchRequest) -> Optional[RawLead]:
        try:
            page.goto(place_url, wait_until="domcontentloaded", timeout=self.detail_timeout_ms)
            page.wait_for_timeout(self.detail_pause_ms)
        except Exception:  # noqa: BLE001 - skip a bad place
            return None

        name_el = page.query_selector("h1")
        name = name_el.inner_text().strip() if name_el else None
        if not name or name.lower() == "results":
            return None

        phone = self._attr_label(page, "button[data-item-id^='phone']")
        website = None
        web_el = page.query_selector("a[data-item-id='authority']")
        if web_el:
            website = web_el.get_attribute("href") or _clean_label(web_el.get_attribute("aria-label"))
        address = self._attr_label(page, "button[data-item-id='address']")

        return RawLead(
            company_name=name,
            source=self.key,
            source_url=place_url,
            phone_raw=phone,
            website=website,
            address=address,
            city=req.city,
            governorate=req.governorate,
            country=req.country,
            category=req.category,
        )

    @staticmethod
    def _attr_label(page, selector: str) -> Optional[str]:
        el = page.query_selector(selector)
        if not el:
            return None
        return _clean_label(el.get_attribute("aria-label")) or _clean_label(el.inner_text())
