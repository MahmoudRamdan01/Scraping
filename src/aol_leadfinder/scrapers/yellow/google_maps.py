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

    SCROLL_ROUNDS = 8
    SCROLL_PAUSE_MS = 1600
    DETAIL_PAUSE_MS = 1500

    def _insecure(self) -> bool:
        import os

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
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3500)
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
        for _ in range(self.SCROLL_ROUNDS):
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
            page.wait_for_timeout(self.SCROLL_PAUSE_MS)
        return seen[: max(want, 0)]

    def _scrape_place(self, page, place_url: str, req: SearchRequest) -> Optional[RawLead]:
        try:
            page.goto(place_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(self.DETAIL_PAUSE_MS)
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
