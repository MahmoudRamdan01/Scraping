"""World Shipping Directory (wsdconnect.com) — real GREEN source.

Verified against the live site: listing cards are ``<div class="listing-card">``
with the detail URL in an ``onclick`` attribute, a ``.listing-company-name``,
a ``.listing-category-tag``, and a contact block with a ``mailto:`` email and
the company's website link. There's no phone in the listing — it can be filled
later from the website via the optional Company Intelligence crawl. Global
directory, so results are filtered to the requested country.
"""
from __future__ import annotations

import re
from typing import Iterator, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..base import BaseScraper, RawLead, SearchRequest
from ..http import fetch_html

_FREIGHT_HINTS = ("freight", "forward", "logistic", "customs", "truck", "shipping", "cargo", "clearance")
_ONCLICK_RE = re.compile(r"window\.location\s*=\s*'([^']+)'")
_SOCIAL = ("facebook", "twitter", "linkedin", "youtube", "instagram", "google", "whatsapp", "pinterest", "t.me")


def _text(el) -> Optional[str]:
    return el.get_text(" ", strip=True) if el else None


def _is_freight(category: Optional[str]) -> bool:
    return not category or any(h in category.lower() for h in _FREIGHT_HINTS)


class WsdConnectScraper(BaseScraper):
    key = "wsdconnect"
    label = "World Shipping Directory (wsdconnect.com)"
    tier = "green"

    LISTING_SELECTOR = "div.listing-card"
    NAME_SELECTOR = ".listing-company-name"
    CATEGORY_SELECTOR = ".listing-category-tag"
    LOCATION_SELECTOR = ".listing-meta"

    MAX_PAGES = 20
    GIVE_UP_AFTER_EMPTY = 6

    def _base_url(self) -> str:
        return self.meta.get("base_url", "https://wsdconnect.com")

    def _page_param(self) -> str:
        return self.meta.get("page_param", "page")

    def _search_url(self, service: str, page: int) -> str:
        base = f"{self._base_url()}/listings?search={quote(service)}"
        return f"{base}&{self._page_param()}={page}" if page > 1 else base

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        if not _is_freight(req.category):
            return
        # It's a global directory — search by country to surface country-specific
        # companies, falling back to the category term.
        service = req.country or req.category or "Freight Forwarding"
        country = (req.country or "").strip().lower()
        seen: set[str] = set()
        emitted = 0
        empty_streak = 0
        for page in range(1, self.MAX_PAGES + 1):
            html = fetch_html(self._search_url(service, page))
            leads = self.parse_listing(html, category=req.category)
            if not leads:
                return
            new_on_page = 0
            for lead in leads:
                blob = f"{lead.address or ''} {lead.country or ''} {lead.company_name or ''}".lower()
                if country and country not in blob:
                    continue
                key = lead.source_url or lead.company_name
                if key in seen:
                    continue
                seen.add(key)
                new_on_page += 1
                emitted += 1
                yield lead
                if emitted >= req.max_results:
                    return
            empty_streak = empty_streak + 1 if new_on_page == 0 else 0
            if empty_streak >= self.GIVE_UP_AFTER_EMPTY:
                return
            self.polite_sleep()

    @classmethod
    def parse_listing(cls, html: str, *, category: Optional[str] = None) -> list[RawLead]:
        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []
        for card in soup.select(cls.LISTING_SELECTOR):
            name = _text(card.select_one(cls.NAME_SELECTOR))
            if not name:
                continue

            source_url = None
            match = _ONCLICK_RE.search(card.get("onclick", ""))
            if match:
                source_url = match.group(1)

            email = None
            mail = card.select_one("a[href^='mailto:']")
            if mail is not None:
                email = mail["href"][7:].split("?")[0].strip()

            website = None
            for a in card.select("a[href^='http']"):
                low = a["href"].lower()
                if "wsdconnect.com" in low or any(s in low for s in _SOCIAL):
                    continue
                website = a["href"]
                break

            location = _text(card.select_one(cls.LOCATION_SELECTOR))
            city = country = None
            if location and "," in location:
                parts = [p.strip() for p in location.split(",")]
                city, country = parts[0], parts[-1]
            elif location:
                country = location

            leads.append(
                RawLead(
                    company_name=name,
                    source=cls.key,
                    source_url=source_url,
                    email=email,
                    website=website,
                    city=city,
                    country=country,
                    address=location,
                    category=_text(card.select_one(cls.CATEGORY_SELECTOR)) or category,
                )
            )
        return leads
