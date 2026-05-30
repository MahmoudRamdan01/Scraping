"""Deduplication keys.

Matching priority: normalised phone (E.164) > website domain > (name + city).
The persistence layer (storage/db.py) uses these to upsert instead of inserting
duplicates across re-runs.
"""
from __future__ import annotations

from typing import Any


def match_keys(lead: Any) -> list[tuple[str, Any]]:
    """Ordered candidate keys used to find an existing lead."""
    keys: list[tuple[str, Any]] = []
    if getattr(lead, "phone_e164", None):
        keys.append(("phone_e164", lead.phone_e164))
    if getattr(lead, "domain", None):
        keys.append(("domain", lead.domain))
    name_norm = getattr(lead, "company_name_norm", None)
    if name_norm:
        keys.append(("name_city", (name_norm, getattr(lead, "city", None))))
    return keys
