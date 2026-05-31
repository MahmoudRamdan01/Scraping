"""World Shipping Directory (wsdconnect.com) — real GREEN source.

Listing cards (server-rendered, confirmed) give company name, location, email and
**website**. Phone lives on the company detail page, so this scraper does a
two-stage fetch: listing -> per-company detail (generic phone extraction).

It's a global directory, so results are filtered to the requested country.
The website it captures is exactly what the Company Intelligence engine needs.
"""
from __future__ import annotations

from typing import Iterator, Optional
from urllib.parse import quote, urljoin

from ..base import BaseScraper, RawLead, SearchRequest
from ..http import extract_emails_from_html, extract_phone_from_html, fetch_html

_FREIGHT_HINTS = ("freight", "forward", "logistic", "customs", "truck", "shipping", "cargo", "clearance")


def _text(el) -> Optional[str]:
    return el.get_text(strip=True) if el else None


def _is_freight(category: Optional[str]) -> bool:
    return not category or any(h in category.lower() for h in _FREIGHT_HINTS)


class WsdConnectScraper(BaseScraper):
    key = "wsdconnect"
    label = "World Shipping Directory (wsdconnect.com)"
    tier = "green"

    LISTING_SELECTOR = "div.company-card"
    NAME_SELECTOR = ".company-name a"
    LOCATION_SELECTOR = ".company-location"
    EMAIL_SELECTOR = ".company-email"
    WEBSITE_SELECTOR = ".company-website"
    DETAIL_SELECTOR = ".view-details-link"

    MAX_PAGES = 20
    fetch_details = True

    def _base_url(self) -> str:
        return self.meta.get("base_url", "https://wsdconnect.com")

    def _page_param(self) -> str:
        return self.meta.get("page_param", "page")

    def _search_url(self, service: str, page: int) -> str:
        base = f"{self._base_url()}/listings?search={quote(service)}"
        return f"{base}&{self._page_param()}={page}" if page > 1 else base

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        if not _is_freight(req.category):
            return  # WSD only lists shipping/logistics companies
        service = req.category or "Freight Forwarding"
        country = (req.country or "").strip().lower()
        emitted = 0
        for page in range(1, self.MAX_PAGES + 1):
            html = fetch_html(self._search_url(service, page))
            leads = self.parse_listing(html, base_url=self._base_url(), category=req.category)
            new_on_page = 0
            for lead in leads:
                location = " ".join(filter(None, [lead.country, lead.address])).lower()
                if country and country not in location:
                    continue
                new_on_page += 1
                if self.fetch_details and lead.source_url and not lead.phone_raw:
                    self._enrich_from_detail(lead)
                    self.polite_sleep()
                emitted += 1
                yield lead
                if emitted >= req.max_results:
                    return
            if new_on_page == 0:
                return
            self.polite_sleep()

    def _enrich_from_detail(self, lead: RawLead) -> None:
        try:
            html = fetch_html(lead.source_url)
        except Exception:  # noqa: BLE001 - detail enrichment is best-effort
            return
        lead.phone_raw = extract_phone_from_html(html)
        if not lead.email:
            emails = extract_emails_from_html(html)
            if emails:
                lead.email = emails[0]

    @classmethod
    def parse_listing(
        cls,
        html: str,
        *,
        base_url: str = "https://wsdconnect.com",
        category: Optional[str] = None,
    ) -> list[RawLead]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []
        for card in soup.select(cls.LISTING_SELECTOR):
            name_el = card.select_one(cls.NAME_SELECTOR) or card.select_one(".company-name")
            name = _text(name_el)
            if not name:
                continue

            href = name_el.get("href") if (name_el and name_el.has_attr("href")) else None
            if not href:
                detail = card.select_one(cls.DETAIL_SELECTOR)
                href = detail["href"] if (detail and detail.get("href")) else None
            source_url = urljoin(base_url, href) if href else None

            location = _text(card.select_one(cls.LOCATION_SELECTOR))
            city = country = None
            if location and "," in location:
                parts = [p.strip() for p in location.split(",")]
                city, country = parts[0], parts[-1]
            elif location:
                country = location

            email = None
            email_el = card.select_one(cls.EMAIL_SELECTOR)
            if email_el is not None:
                href2 = email_el.get("href", "")
                email = href2[7:].strip() if href2.startswith("mailto:") else _text(email_el)

            web_el = card.select_one(cls.WEBSITE_SELECTOR)
            website = None
            if web_el is not None:
                website = web_el.get("href") or _text(web_el)

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
                    category=category,
                )
            )
        return leads
