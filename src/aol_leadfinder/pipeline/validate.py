"""Structural validation — *can this record be stored as a real lead at all?*

This is deliberately distinct from ``pipeline/filters.py``, which encodes the
sales team's *quality* preferences (followers, activity, "must have a phone").
Validation is about data *integrity*: a record with no identity, no contact
channel, or a malformed phone is **broken data**, not a low-quality lead.

Broken records are quarantined (kept but flagged) rather than silently dropped,
so nothing corrupt enters the working lead list while staying visible for review.

Returns ``(ok, reason)``; ``reason`` is a short machine code when invalid.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# A usable name needs at least two "word" chars (\w already covers Arabic in
# Python 3; the explicit Arabic block mirrors normalize.py and is belt-and-braces).
# This rejects junk like "-", "...", or a stray single character.
_NAME_ALNUM = re.compile(r"[\w؀-ۿ]")
# E.164 shape: a leading + and 6–15 digits. normalize_lead already guarantees this
# for phone_e164, so the check is purely defensive against a bad upstream value.
_E164 = re.compile(r"\+\d{6,15}")


def _has_contact(lead: Any) -> bool:
    return bool(
        getattr(lead, "phone_e164", None)
        or getattr(lead, "email", None)
        or getattr(lead, "website", None)
        or getattr(lead, "domain", None)
    )


def validate_lead(lead: Any) -> tuple[bool, Optional[str]]:
    """Structural integrity gate. Order: identity -> junk -> contact -> phone shape."""
    name = (getattr(lead, "company_name", None) or "").strip()
    if not name:
        return False, "no_identity"
    if len(_NAME_ALNUM.findall(name)) < 2:
        return False, "junk_name"

    if not _has_contact(lead):
        return False, "no_contact"

    phone = getattr(lead, "phone_e164", None)
    if phone and not _E164.fullmatch(phone):
        return False, "bad_phone"

    return True, None
