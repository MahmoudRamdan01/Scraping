"""Yellow Pages Egypt (yellowpages.com.eg) — YELLOW source (Phase 2).

Reachable with plain ``requests`` (Cloudflare serves the search pages), so this
inherits the central retry in :func:`fetch_html` rather than needing Playwright.
Treat it as best-effort: if the listing markup shifts or Cloudflare starts
challenging, the parser yields nothing instead of raising.

Two-level shape, verified against the live site and pinned in fixtures:

* Search results live in ``.item-row`` blocks (``a.item-title`` = name + profile
  link, ``.address-text`` = address, ``.category a`` = category). The company id
  is the trailing number in the profile URL ``/en/profile/<slug>/<id>``.
* Phones are NOT in the listing — the site loads them per company from a small
  JSON endpoint ``/en/getPhones/<id>/false`` -> ``[[mobiles], [landlines], [fax]]``.
  ``search`` fetches that per lead (capped + polite); the pure parsers stay
  network-free so they can be unit-tested against the fixtures.
"""
from __future__ import annotations

import json
import re
from typing import Iterator, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..base import BaseScraper, RawLead, SearchRequest
from ..http import fetch_html

_ID_RE = re.compile(r"/profile/[^/]+/(\d+)")
_PHONEISH_RE = re.compile(r"[\d\-+()\s]{7,}")


def _text(el) -> Optional[str]:
    return el.get_text(" ", strip=True) if el else None


def _abs_url(href: str, base_url: str) -> Optional[str]:
    """Normalise a listing href (often protocol-relative ``//host/...``)."""
    href = (href or "").split("?")[0].strip()
    if not href:
        return None
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return base_url.rstrip("/") + href
    return href


class YellowPagesEgScraper(BaseScraper):
    key = "yellowpages_eg"
    label = "Yellow Pages Egypt (yellowpages.com.eg)"
    tier = "yellow"

    LISTING_SELECTOR = ".item-row"
    NAME_SELECTOR = "a.item-title"
    ADDRESS_SELECTOR = ".address-text"
    CATEGORY_SELECTOR = ".category a"

    MAX_PAGES = 15
    GIVE_UP_AFTER_EMPTY = 3

    def _base_url(self) -> str:
        return self.meta.get("base_url", "https://www.yellowpages.com.eg")

    @staticmethod
    def _query(req: SearchRequest) -> str:
        for term in (*(req.keywords or []), req.category, req.role):
            if term and term.strip():
                return term.strip()
        return ""

    def _search_url(self, query: str, page: int) -> str:
        base = f"{self._base_url()}/en/search/{quote(query, safe='')}"
        return f"{base}/p{page}" if page > 1 else base

    def _fetch_phones(self, company_id: str) -> list[str]:
        """Best-effort: pull a company's phones from the JSON endpoint."""
        url = f"{self._base_url()}/en/getPhones/{company_id}/false"
        try:
            return self.parse_phones(fetch_html(url))
        except Exception:  # noqa: BLE001 - phones are optional, never fail the scrape
            return []

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        query = self._query(req)
        if not query:
            return
        want_gov = (req.governorate or "").strip().lower()
        want_city = (req.city or "").strip().lower()
        seen: set[str] = set()
        emitted = 0
        empty_streak = 0
        for page in range(1, self.MAX_PAGES + 1):
            try:
                html = fetch_html(self._search_url(query, page))
            except Exception:  # noqa: BLE001 - yellow tier degrades quietly
                return
            leads = self.parse_listing(html, base_url=self._base_url(), category=req.category)
            if not leads:
                return
            new_on_page = 0
            for lead in leads:
                key = lead.source_url or lead.company_name
                if key in seen:
                    continue
                seen.add(key)
                if want_gov and want_gov not in (lead.governorate or "").lower():
                    continue
                if want_city and want_city not in (lead.city or "").lower():
                    continue
                new_on_page += 1

                company_id = lead.raw.get("yp_id")
                if company_id:
                    phones = self._fetch_phones(company_id)
                    if phones:
                        lead.phone_raw = phones[0]
                        lead.extra_phones = phones[1:]

                emitted += 1
                yield lead
                if emitted >= req.max_results:
                    return
                self.polite_sleep()
            empty_streak = empty_streak + 1 if new_on_page == 0 else 0
            if empty_streak >= self.GIVE_UP_AFTER_EMPTY:
                return
            self.polite_sleep()

    @classmethod
    def parse_listing(
        cls,
        html: str,
        *,
        base_url: str = "https://www.yellowpages.com.eg",
        category: Optional[str] = None,
    ) -> list[RawLead]:
        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []
        for row in soup.select(cls.LISTING_SELECTOR):
            name_el = row.select_one(cls.NAME_SELECTOR)
            name = _text(name_el)
            if not name_el or not name:
                continue
            href = name_el.get("href", "")
            source_url = _abs_url(href, base_url)
            id_match = _ID_RE.search(href)

            address = _text(row.select_one(cls.ADDRESS_SELECTOR))
            city = governorate = None
            if address:
                parts = [p.strip() for p in address.rstrip(" .").split(",") if p.strip()]
                if len(parts) >= 2:
                    city, governorate = parts[-2], parts[-1]
                elif parts:
                    governorate = parts[-1]

            leads.append(
                RawLead(
                    company_name=name,
                    source=cls.key,
                    source_url=source_url,
                    address=address,
                    city=city,
                    governorate=governorate,
                    country="Egypt",
                    category=_text(row.select_one(cls.CATEGORY_SELECTOR)) or category,
                    raw={"yp_id": id_match.group(1)} if id_match else {},
                )
            )
        return leads

    @classmethod
    def parse_phones(cls, payload: str) -> list[str]:
        """Flatten the ``/getPhones`` JSON ``[[...],[...],[...]]`` into raw strings.

        Order is preserved (mobiles first as the site returns them) and duplicates
        dropped. Falls back to a permissive regex if the body isn't valid JSON.
        """
        out: list[str] = []

        def add(value) -> None:
            if isinstance(value, str):
                v = value.strip()
                if v and v not in out:
                    out.append(v)

        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            for m in _PHONEISH_RE.findall(payload or ""):
                add(m)
            return out

        def walk(node) -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item)
            else:
                add(node)

        walk(data)
        return out
