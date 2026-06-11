"""Textile Export Council of Egypt (textile-egypt.org) — GREEN source.

The council publishes a directory of its member companies — ~150 Egyptian
textile MANUFACTURERS / exporters (spinning, weaving, fabrics, garments), i.e.
exactly the end-customers a freight team sells to (verified exporters = real
shipping demand). Plain ``requests`` static HTML, so it inherits the central
retry in :func:`fetch_html`.

Two-level shape, verified live and pinned in fixtures:

* The members page is a grid of ``div.grid-item`` cards; each card has an
  ``img[alt]`` (company name) and an ``a[href^="members/"]`` to a detail page.
* Contacts live on the detail page as *labelled text* (no tel:/mailto: links)
  alongside ad-spam, so they're harvested with the quality-first primitives in
  ``scrapers.http`` (validated E.164 phones + junk-filtered emails) plus a
  WEBSITE/ADDRESS label match. ``search`` fetches each member page (capped,
  polite); the pure parsers stay network-free for unit testing.
"""
from __future__ import annotations

import re
from typing import Iterator, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base import BaseScraper, RawLead, SearchRequest
from ..http import extract_emails_from_html, extract_phones, fetch_html

_COUNCIL_DOMAIN = "textile-egypt.org"
_WEBSITE_RE = re.compile(r"\bWEBSITE\b[:\s]+(https?://[^\s\"<]+)", re.I)
_ADDR_RE = re.compile(
    r"\bADDRESS\b[:\s]+(.+?)(?:\s+(?:OFFICE|FACTORY|HEAD|SHOWROOM|WEBSITE|E-?MAILS?|"
    r"PHONES?|MOBILE|FAX|TEL|CONTACT|GENERAL)\b|$)",
    re.I,
)
# The directory is all-textile; only run it for textile-related searches so it
# doesn't pollute an unrelated multi-source run (same idea as freightclub).
_TEXTILE_HINTS = (
    "textile", "garment", "clothing", "fashion", "apparel",
    "spinning", "weaving", "fabric", "yarn", "cotton",
)


def _is_textile(category: Optional[str]) -> bool:
    return not category or any(h in category.lower() for h in _TEXTILE_HINTS)


class TextileCouncilScraper(BaseScraper):
    key = "textile_council"
    label = "Textile Export Council of Egypt (textile-egypt.org)"
    tier = "green"

    LISTING_SELECTOR = ".members .grid-item"

    def _base_url(self) -> str:
        return self.meta.get("base_url", "https://textile-egypt.org/textile-egypt.org")

    def _members_url(self) -> str:
        return self._base_url().rstrip("/") + "/members.html"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        if not _is_textile(req.category):
            return
        try:
            html = fetch_html(self._members_url())
        except Exception:  # noqa: BLE001 - green tier degrades quietly
            return
        emitted = 0
        for lead in self.parse_listing(html, base_url=self._base_url()):
            if not lead.source_url:
                continue
            try:
                detail = self.parse_detail(fetch_html(lead.source_url))
            except Exception:  # noqa: BLE001 - skip a bad member page, keep going
                detail = {"phones": [], "emails": [], "website": None, "address": None}
            if detail["phones"]:
                lead.phone_raw = detail["phones"][0]
                lead.extra_phones = detail["phones"][1:] or None
            if detail["emails"]:
                lead.email = detail["emails"][0]
            lead.website = detail["website"]
            if detail["address"]:
                lead.address = detail["address"]
            yield lead
            emitted += 1
            if emitted >= req.max_results:
                return
            self.polite_sleep()

    @classmethod
    def parse_listing(
        cls,
        html: str,
        *,
        base_url: str = "https://textile-egypt.org/textile-egypt.org",
    ) -> list[RawLead]:
        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []
        seen: set[str] = set()
        for card in soup.select(cls.LISTING_SELECTOR):
            img = card.select_one("img[alt]")
            link = card.select_one("a[href*='members/']")
            if img is None or link is None:
                continue
            name = (img.get("alt") or "").strip()
            href = (link.get("href") or "").strip()
            if not name or not href or href in seen:
                continue
            seen.add(href)
            leads.append(
                RawLead(
                    company_name=name,
                    source=cls.key,
                    source_url=urljoin(base_url.rstrip("/") + "/", href),
                    category="Textiles",
                    country="Egypt",
                )
            )
        return leads

    @classmethod
    def parse_detail(cls, html: str) -> dict:
        """Harvest contacts from a member page (labelled text + ad-spam)."""
        phones = extract_phones(html, "EG")
        emails = [e for e in extract_emails_from_html(html) if _COUNCIL_DOMAIN not in e]
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        website_match = _WEBSITE_RE.search(text)
        address_match = _ADDR_RE.search(text)
        return {
            "phones": phones,
            "emails": emails,
            "website": website_match.group(1) if website_match else None,
            "address": address_match.group(1).strip() if address_match else None,
        }
