"""Multi-page website crawler for company enrichment.

Given a company website it fetches the homepage, discovers a few key sub-pages
(About / Services / Products / Contact), combines their text, then:
- classifies the company type (Importer/Exporter/Manufacturer/...),
- extracts emails and phones,
- detects target markets,
- computes a richer Shipping Intent Score.

``fetch`` is injectable so the crawl logic is fully unit-testable offline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..scrapers.http import (
    extract_emails_from_html,
    extract_phones,
    extract_whatsapp_numbers,
    fetch_html,
)
from .intelligence import classify_company
from .markets import detect_markets

# Contact-ish pages first — that's where real numbers/emails live.
_CONTACT_HINTS = ["contact", "تواصل", "اتصل", "اتصل-بنا", "call", "reach"]
_SUBPAGE_HINTS = _CONTACT_HINTS + [
    "about", "services", "service", "products", "product", "company",
    "profile", "عن", "نبذة", "من-نحن", "خدمات", "المنتجات",
]


@dataclass
class WebsiteIntel:
    company_type: str = "Unknown"
    shipping_intent: int = 0
    signals: list[str] = field(default_factory=list)
    has_online_store: bool = False
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    whatsapp: list[str] = field(default_factory=list)
    markets: list[str] = field(default_factory=list)
    pages_crawled: int = 0


def discover_subpages(home_html: str, base_url: str, limit: int = 3) -> list[str]:
    soup = BeautifulSoup(home_html, "lxml")
    base_host = urlparse(base_url).netloc.lower()
    contact: list[str] = []
    other: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc.lower() != base_host:
            continue
        haystack = parsed.path.lower() + " " + (a.get_text(" ", strip=True) or "").lower()
        if not any(h in haystack for h in _SUBPAGE_HINTS):
            continue
        key = parsed.path.rstrip("/")
        if not key or key in seen or full == base_url:
            continue
        seen.add(key)
        (contact if any(h in haystack for h in _CONTACT_HINTS) else other).append(full)
    # Contact pages first — that's where the real numbers live.
    return (contact + other)[:limit]


def crawl_website(
    url: str,
    *,
    category: Optional[str] = None,
    region: str = "EG",
    max_pages: int = 4,
    fetch: Callable[[str], str] = fetch_html,
    delay: float = 0.3,
) -> WebsiteIntel:
    htmls: list[str] = []
    try:
        htmls.append(fetch(url))
    except Exception:  # noqa: BLE001 - unreachable site -> empty result
        return WebsiteIntel()

    for sub in discover_subpages(htmls[0], url, limit=max(0, max_pages - 1)):
        try:
            htmls.append(fetch(sub))
            if delay:
                time.sleep(delay)
        except Exception:  # noqa: BLE001 - skip bad sub-pages
            continue

    text = " ".join(BeautifulSoup(h, "lxml").get_text(" ", strip=True) for h in htmls)
    intel = classify_company(text, category)

    emails: list[str] = []
    phones: list[str] = []
    whatsapp: list[str] = []
    for h in htmls:
        for email in extract_emails_from_html(h):
            if email not in emails:
                emails.append(email)
        for phone in extract_phones(h, region):
            if phone not in phones:
                phones.append(phone)
        for wa in extract_whatsapp_numbers(h, region):
            if wa not in whatsapp:
                whatsapp.append(wa)

    markets = detect_markets(text)
    non_local = [m for m in markets if not m.startswith("Local")]
    intent = min(intel.shipping_intent + 5 * len(non_local) + (10 if intel.has_online_store else 0), 100)

    return WebsiteIntel(
        company_type=intel.company_type,
        shipping_intent=intent,
        signals=intel.signals,
        has_online_store=intel.has_online_store,
        emails=emails,
        phones=phones,
        whatsapp=whatsapp,
        markets=markets,
        pages_crawled=len(htmls),
    )
