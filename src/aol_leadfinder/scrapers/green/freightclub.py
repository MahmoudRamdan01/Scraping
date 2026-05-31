"""Freight Club Directory (freightclub.net) — real GREEN source.

Verified against the live site: it's an Elementor page where each company is a
name link to ``/companies/<slug>/`` followed by a ``tel:`` phone link. We pair
each phone with the nearest preceding company link (document order), which is
robust to the generated Elementor wrapper markup.
"""
from __future__ import annotations

import re
from typing import Iterator, Optional
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from ..base import BaseScraper, RawLead, SearchRequest
from ..http import fetch_html

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

_SLUG_RE = re.compile(r"/companies/([^/?#]+)/?$")
_SKIP_SLUGS = {"feed"}


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

    MAX_PAGES = 20

    def _base_url(self) -> str:
        return self.meta.get("base_url", "https://www.freightclub.net")

    def _page_param(self) -> str:
        return self.meta.get("page_param", "page")

    def _search_url(self, fc_category: str, country: str, page: int) -> str:
        base = f"{self._base_url()}/companies?category={quote(fc_category)}&country={quote(country)}"
        return f"{base}&{self._page_param()}={page}" if page > 1 else base

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        fc_category = _map_category(req.category)
        if fc_category is None:
            return
        country = req.country or "Egypt"
        seen: set[str] = set()
        emitted = 0
        for page in range(1, self.MAX_PAGES + 1):
            html = fetch_html(self._search_url(fc_category, country, page))
            leads = self.parse_listing(
                html, base_url=self._base_url(), country=country, category=req.category or fc_category
            )
            new_on_page = 0
            for lead in leads:
                key = lead.source_url or lead.company_name
                if key in seen:
                    continue
                seen.add(key)
                new_on_page += 1
                emitted += 1
                yield lead
                if emitted >= req.max_results:
                    return
            if new_on_page == 0:
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
        current: Optional[dict] = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            match = _SLUG_RE.search(href)
            if match and match.group(1) not in _SKIP_SLUGS:
                name = a.get_text(" ", strip=True)
                if name and len(name) > 1:
                    current = {"name": name, "url": urljoin(base_url, href)}
            elif href.startswith("tel:") and current is not None:
                leads.append(
                    RawLead(
                        company_name=current["name"],
                        source=cls.key,
                        source_url=current["url"],
                        phone_raw=href[4:].strip(),
                        country=country,
                        category=category,
                    )
                )
                current = None
        return leads
