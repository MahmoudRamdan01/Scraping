"""EgyDir scraper (egydir.com) — reference implementation for a GREEN source.

The parsing is split into a pure ``parse_listing(html)`` classmethod (unit-tested
against tests/fixtures/egydir_sample.html) and a thin ``search()`` that fetches.

NOTE ON SELECTORS: egydir.com's live markup is not pinned here, so the CSS
selectors below are PROVISIONAL and validated only against the fixture. Before
the first live run, confirm them against the real site (use scripts/smoke.py)
and adjust the ``*_SELECTOR`` class attributes. If selectors don't match, the
parser simply yields nothing (it fails safe, not loud).
"""
from __future__ import annotations

from typing import Iterator, Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from ..base import BaseScraper, RawLead, SearchRequest

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.8",
}


def _text(el) -> Optional[str]:
    return el.get_text(strip=True) if el else None


class EgyDirScraper(BaseScraper):
    key = "egydir"
    label = "EgyDir (egydir.com)"
    tier = "green"

    LISTING_SELECTOR = "div.company-card"
    NAME_SELECTOR = ".company-name"
    PHONE_TEL_SELECTOR = "a[href^='tel:']"
    PHONE_TEXT_SELECTOR = ".company-phone"
    WEBSITE_SELECTOR = "a.company-website"
    ADDRESS_SELECTOR = ".company-address"
    CATEGORY_SELECTOR = ".company-category"

    def _base_url(self) -> str:
        return self.meta.get("base_url", "https://www.egydir.com")

    def _search_url(self, req: SearchRequest) -> str:
        query = (req.category or "").strip()
        if req.keywords:
            query = f"{query} {req.keywords[0]}".strip()
        location = (req.city or req.governorate or "").strip()
        return f"{self._base_url()}/search?q={quote(query)}&location={quote(location)}"

    def _fetch(self, url: str) -> str:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        html = self._fetch(self._search_url(req))
        for lead in self.parse_listing(
            html, base_url=self._base_url(), default_city=req.city, category=req.category
        ):
            yield lead
            self.polite_sleep()

    @classmethod
    def parse_listing(
        cls,
        html: str,
        *,
        base_url: str = "https://www.egydir.com",
        default_city: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[RawLead]:
        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []
        for card in soup.select(cls.LISTING_SELECTOR):
            name_el = card.select_one(cls.NAME_SELECTOR)
            if not name_el:
                continue
            link = name_el.find("a")
            name = _text(link) or _text(name_el)
            if not name:
                continue
            source_url = urljoin(base_url, link["href"]) if (link and link.get("href")) else None

            phone = None
            tel = card.select_one(cls.PHONE_TEL_SELECTOR)
            if tel is not None:
                phone = (tel.get("href", "")[4:].strip()) or _text(tel)
            else:
                phone = _text(card.select_one(cls.PHONE_TEXT_SELECTOR))

            web = card.select_one(cls.WEBSITE_SELECTOR)
            website = web["href"].strip() if (web and web.get("href")) else None

            leads.append(
                RawLead(
                    company_name=name,
                    source=cls.key,
                    source_url=source_url,
                    phone_raw=phone,
                    website=website,
                    address=_text(card.select_one(cls.ADDRESS_SELECTOR)),
                    city=default_city,
                    category=_text(card.select_one(cls.CATEGORY_SELECTOR)) or category,
                )
            )
        return leads
