"""Normalise raw scraped records: phone -> E.164, website -> domain, name key."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from urllib.parse import urlparse

import phonenumbers

from ..scrapers.base import RawLead

_WS = re.compile(r"\s+")
# Keep ASCII word chars + Arabic block for the normalised name key
_NAME_CLEAN = re.compile(r"[^\w؀-ۿ]+")


def normalize_phone(raw: Optional[str], region: str = "EG") -> Optional[str]:
    """Parse/validate a phone number to E.164, or None if invalid."""
    if not raw:
        return None
    try:
        num = phonenumbers.parse(str(raw).strip(), region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num):
        return None
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def normalize_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = str(url).strip()
    if not url:
        return None
    if "://" not in url:
        url = "http://" + url
    netloc = urlparse(url).netloc.lower().split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None


def normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    s = _NAME_CLEAN.sub(" ", str(name).lower())
    return _WS.sub(" ", s).strip()


def _clean_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    e = str(email).strip().lower()
    return e if "@" in e and "." in e.split("@")[-1] else None


@dataclass
class NormalizedLead:
    company_name: str
    company_name_norm: str
    source: str
    source_url: Optional[str] = None
    phone_e164: Optional[str] = None
    phone_raw: Optional[str] = None
    extra_phones: list[str] = field(default_factory=list)
    email: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    governorate: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    social_links: dict = field(default_factory=dict)
    followers: Optional[int] = None
    last_activity_date: Optional[date] = None
    rating: Optional[float] = None
    branches: Optional[int] = None
    has_online_store: Optional[bool] = None
    company_type: Optional[str] = None
    shipping_intent: Optional[int] = None
    score: int = 0
    tier: str = "Weak"
    score_reasons: list = field(default_factory=list)


def normalize_lead(raw: RawLead, *, default_country: str = "Egypt", region: str = "EG") -> NormalizedLead:
    company = (raw.company_name or "").strip()

    candidates: list[str] = []
    if raw.phone_raw:
        candidates.append(raw.phone_raw)
    candidates.extend(raw.extra_phones or [])
    norm_phones: list[str] = []
    for cand in candidates:
        e164 = normalize_phone(cand, region)
        if e164 and e164 not in norm_phones:
            norm_phones.append(e164)
    primary = norm_phones[0] if norm_phones else None
    extras = norm_phones[1:]

    website = raw.website.strip() if raw.website else None
    domain = normalize_domain(website)
    if website and "://" not in website:
        website = "https://" + website

    return NormalizedLead(
        company_name=company,
        company_name_norm=normalize_name(company),
        source=raw.source,
        source_url=raw.source_url,
        phone_e164=primary,
        phone_raw=raw.phone_raw,
        extra_phones=extras,
        email=_clean_email(raw.email),
        website=website,
        domain=domain,
        address=raw.address,
        city=raw.city,
        governorate=raw.governorate,
        country=raw.country or default_country,
        category=raw.category,
        description=raw.description,
        social_links=raw.social_links or {},
        followers=raw.followers,
        last_activity_date=raw.last_activity_date,
        rating=raw.rating,
        branches=raw.branches,
        has_online_store=raw.has_online_store,
    )
