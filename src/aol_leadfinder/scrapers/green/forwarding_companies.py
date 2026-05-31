"""Forwarding Companies (forwardingcompanies.com) — real GREEN source.

Verified against the live site: the country page (``/in/egypt``) is a clean,
server-rendered table of ``<tr class="company-data">`` rows (≈343 Egyptian
companies on one page). Each row gives:
- company name  (``data-name`` attr + ``.company-name a`` -> ``/company/<slug>``)
- location      (``.address-wrap`` -> "City, Country")
- a DESCRIPTION (``.about-title`` + ``.about-description``) which the Company
  Intelligence engine classifies offline — no website crawl needed.

The company's own website (the only direct contact here) lives on the detail
page, fetched best-effort up to ``max_results``.
"""
from __future__ import annotations

from typing import Iterator, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base import BaseScraper, RawLead, SearchRequest
from ..http import fetch_html

_SOCIAL = ("facebook", "twitter", "linkedin", "youtube", "instagram", "google", "whatsapp", "pinterest", "t.me")


def _text(el) -> Optional[str]:
    return el.get_text(" ", strip=True) if el else None


class ForwardingCompaniesScraper(BaseScraper):
    key = "forwarding_companies"
    label = "Forwarding Companies (forwardingcompanies.com)"
    tier = "green"

    LISTING_SELECTOR = "tr.company-data"
    fetch_details = True

    def _base_url(self) -> str:
        return self.meta.get("base_url", "https://forwardingcompanies.com")

    def _location_slug(self, req: SearchRequest) -> str:
        loc = (req.city or req.country or "egypt").strip().lower()
        return loc.replace(" ", "-")

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        html = fetch_html(f"{self._base_url()}/in/{self._location_slug(req)}")
        leads = self.parse_listing(html, base_url=self._base_url(), category=req.category)
        emitted = 0
        for lead in leads:
            if self.fetch_details and lead.source_url and not lead.website:
                lead.website = self._website_from_detail(lead.source_url)
                self.polite_sleep()
            emitted += 1
            yield lead
            if emitted >= req.max_results:
                return

    def _website_from_detail(self, url: str) -> Optional[str]:
        try:
            html = fetch_html(url)
        except Exception:  # noqa: BLE001 - best-effort
            return None
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a[href^='http']"):
            href = a.get("href", "")
            low = href.lower()
            if "forwardingcompanies.com" in low or any(s in low for s in _SOCIAL):
                continue
            return href
        return None

    @classmethod
    def parse_listing(
        cls,
        html: str,
        *,
        base_url: str = "https://forwardingcompanies.com",
        category: Optional[str] = None,
    ) -> list[RawLead]:
        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []
        for row in soup.select(cls.LISTING_SELECTOR):
            link = row.select_one(".company-name a")
            name = (row.get("data-name") or _text(link) or "").strip()
            if not name:
                continue
            source_url = urljoin(base_url, link["href"]) if (link and link.get("href")) else None

            location = _text(row.select_one(".address-wrap"))
            city = country = None
            if location and "," in location:
                parts = [p.strip() for p in location.split(",")]
                city, country = parts[0], parts[-1]
            elif location:
                country = location

            description = " ".join(
                p for p in [_text(row.select_one(".about-title")), _text(row.select_one(".about-description"))] if p
            ) or None

            leads.append(
                RawLead(
                    company_name=name,
                    source=cls.key,
                    source_url=source_url,
                    city=city,
                    country=country,
                    address=location,
                    category=category,
                    description=description,
                )
            )
        return leads
