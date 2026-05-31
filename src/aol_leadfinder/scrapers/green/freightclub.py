"""Freight Club Directory (freightclub.net) — first REAL working GREEN source.

Selectors confirmed against the live site (2026): listing cards are server-rendered
(`requests` + BeautifulSoup is enough, no Cloudflare/JS), phone numbers are visible
in each card as a `tel:` link. This is a freight-forwarder directory, so it yields
shipping/logistics companies (ideal Air Ocean Line partners). For non-freight
categories it yields nothing (those live on Google Maps / EgyDir).

Pagination param is set via sources.yaml `page_param` (default "page") and verified
with scripts/smoke.py; the loop stops as soon as a page returns no new companies.
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
    "Accept-Language": "en,ar;q=0.8",
}

# Map our category names to FreightClub's directory categories.
_FREIGHT_CATEGORY_MAP = {
    "freight forwarder": "Freight Forwarder",
    "forwarder": "Freight Forwarder",
    "logistics": "Freight Forwarder",
    "customs": "Customs Clearance Offices",
    "customs clearance": "Customs Clearance Offices",
    "trucking": "Trucking Companies",
    "transport": "Trucking Companies",
}


def _text(el) -> Optional[str]:
    return el.get_text(strip=True) if el else None


def _map_category(category: Optional[str]) -> Optional[str]:
    """Return the FreightClub category for our category, or None if not freight."""
    if not category:
        return "Freight Forwarder"
    low = category.lower()
    for needle, fc_cat in _FREIGHT_CATEGORY_MAP.items():
        if needle in low:
            return fc_cat
    return None


class FreightClubScraper(BaseScraper):
    key = "freightclub"
    label = "Freight Club Directory (freightclub.net)"
    tier = "green"

    LISTING_SELECTOR = "div.company-card"
    NAME_SELECTOR = "h3 a"
    PHONE_SELECTOR = ".phone"
    COUNTRY_SELECTOR = ".country"

    MAX_PAGES = 20

    def _base_url(self) -> str:
        return self.meta.get("base_url", "https://www.freightclub.net")

    def _page_param(self) -> str:
        return self.meta.get("page_param", "page")

    def _search_url(self, fc_category: str, country: str, page: int) -> str:
        base = f"{self._base_url()}/companies?category={quote(fc_category)}&country={quote(country)}"
        return f"{base}&{self._page_param()}={page}" if page > 1 else base

    def _fetch(self, url: str) -> str:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        fc_category = _map_category(req.category)
        if fc_category is None:
            # FreightClub only lists freight/logistics companies.
            return
        country = req.country or "Egypt"
        seen: set[str] = set()
        emitted = 0
        for page in range(1, self.MAX_PAGES + 1):
            html = self._fetch(self._search_url(fc_category, country, page))
            leads = self.parse_listing(
                html, base_url=self._base_url(), country=country, category=req.category or fc_category
            )
            new_on_page = 0
            for lead in leads:
                key = lead.source_url or f"{lead.company_name}|{lead.phone_raw}"
                if key in seen:
                    continue
                seen.add(key)
                new_on_page += 1
                emitted += 1
                yield lead
                if emitted >= req.max_results:
                    return
            if new_on_page == 0:  # no more pages (or pagination param ignored)
                return
            self.polite_sleep()

    @classmethod
    def parse_listing(
        cls,
        html: str,
        *,
        base_url: str = "https://www.freightclub.net",
        country: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[RawLead]:
        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []
        for card in soup.select(cls.LISTING_SELECTOR):
            name_el = card.select_one(cls.NAME_SELECTOR)
            name = _text(name_el)
            if not name:
                continue
            source_url = (
                urljoin(base_url, name_el["href"]) if (name_el and name_el.get("href")) else None
            )

            phone = None
            phone_el = card.select_one(cls.PHONE_SELECTOR)
            if phone_el is not None:
                href = phone_el.get("href", "")
                phone = href[4:].strip() if href.startswith("tel:") else _text(phone_el)

            leads.append(
                RawLead(
                    company_name=name,
                    source=cls.key,
                    source_url=source_url,
                    phone_raw=phone,
                    country=_text(card.select_one(cls.COUNTRY_SELECTOR)) or country,
                    category=category,
                )
            )
        return leads
