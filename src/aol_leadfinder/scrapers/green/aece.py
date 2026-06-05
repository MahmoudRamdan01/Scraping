"""Apparel Export Council of Egypt (aecegy.com) — GREEN source.

~170 Egyptian apparel / garment MANUFACTURERS & exporters (the end-customers a
freight team sells to), via plain requests static HTML so it inherits the
central fetch_html retry. Second of the ranked "export council" sources.

Two-level, verified live and pinned in fixtures:

* /business-directory/ is a member table — each row has the company name and a
  link to its member page.
* The member page carries phones + a postal address; emails are
  Cloudflare-obfuscated and recovered transparently by
  ``scrapers.http.extract_emails_from_html`` (which now decodes data-cfemail).
  ``search`` fetches each member page (capped, polite); the pure parsers stay
  network-free for unit testing.
"""
from __future__ import annotations

import re
from typing import Iterator, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base import BaseScraper, RawLead, SearchRequest
from ..http import extract_emails_from_html, extract_phones, fetch_html

_COUNCIL_DOMAIN = "aecegy.com"
_SOCIAL = ("facebook", "twitter", "linkedin", "youtube", "instagram", "google", "whatsapp", "pinterest", "t.me")
_ADDR_RE = re.compile(
    r"\bADDRESS\b[:\s]+(.+?)(?:\s+(?:TEL|PHONE|MOBILE|FAX|E-?MAILS?|WEBSITE|FACTORY|OFFICE|CONTACT)\b|$)",
    re.I,
)
# All-apparel directory: only run it for apparel-related searches (cf. freightclub).
_APPAREL_HINTS = (
    "apparel", "garment", "clothing", "fashion", "textile",
    "ready", "wear", "cotton", "knit",
)


def _is_apparel(category: Optional[str]) -> bool:
    return not category or any(h in category.lower() for h in _APPAREL_HINTS)


class AECEScraper(BaseScraper):
    key = "aece"
    label = "Apparel Export Council of Egypt (aecegy.com)"
    tier = "green"

    DIRECTORY_PATH = "/business-directory/"
    DETAIL_HINT = "business-directory/"

    def _base_url(self) -> str:
        return self.meta.get("base_url", "https://aecegy.com")

    def _directory_url(self) -> str:
        return self._base_url().rstrip("/") + self.DIRECTORY_PATH

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        if not _is_apparel(req.category):
            return
        try:
            html = fetch_html(self._directory_url())
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
    def parse_listing(cls, html: str, *, base_url: str = "https://aecegy.com") -> list[RawLead]:
        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []
        seen: set[str] = set()
        for row in soup.select("table tr"):
            cells = row.select("td")
            if not cells:
                continue
            link = row.select_one(f"a[href*='{cls.DETAIL_HINT}']")
            name = cells[0].get_text(" ", strip=True)
            href = (link.get("href") or "").strip() if link else None
            if not name or not href or href in seen:
                continue
            seen.add(href)
            leads.append(
                RawLead(
                    company_name=name,
                    source=cls.key,
                    source_url=urljoin(base_url.rstrip("/") + "/", href),
                    category="Garments",
                    country="Egypt",
                )
            )
        return leads

    @classmethod
    def parse_detail(cls, html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        phones = extract_phones(html, "EG")
        emails = [e for e in extract_emails_from_html(html) if _COUNCIL_DOMAIN not in e]
        address_match = _ADDR_RE.search(soup.get_text(" ", strip=True))
        website = None
        for a in soup.select("a[href^='http']"):
            low = (a.get("href") or "").lower()
            if _COUNCIL_DOMAIN in low or any(s in low for s in _SOCIAL):
                continue
            website = a.get("href")
            break
        return {
            "phones": phones,
            "emails": emails,
            "website": website,
            "address": address_match.group(1).strip() if address_match else None,
        }
