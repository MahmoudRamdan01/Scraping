"""Deduplication / merge policy — the single source of truth for the question
"is this the same company we already have?"

MERGE PRIORITY (strongest key first). The first key that matches an existing
lead wins, and the new sighting is *merged* into it instead of inserted:

    1. phone_e164   strongest — a validated E.164 number is a near-unique
                    identifier for a business line.
    2. domain       normalised website host (scheme / "www." stripped).
    3. name_city    EXACT normalised company name + city. A safe last resort.

Deliberately **no fuzzy / approximate name matching.** A false merge — collapsing
two genuinely different companies into one — silently destroys a real lead and is
far worse than keeping a duplicate (which is merely cosmetic and easy to spot
later). So name matching is exact-normalised only: if two records share neither a
phone, a domain, nor an identical normalised name+city, they stay separate.

The persistence layer (storage/db.py: ``_find_existing`` / ``upsert_lead``)
consumes ``match_keys`` in this order to upsert instead of duplicating across runs.
"""
from __future__ import annotations

from typing import Any

# Ordered strongest -> weakest. Kept as an explicit, importable constant so the
# policy is stated once here, not buried implicitly in match_keys() control flow.
MERGE_PRIORITY: tuple[str, ...] = ("phone_e164", "domain", "name_city")


def match_keys(lead: Any) -> list[tuple[str, Any]]:
    """Candidate keys for finding an existing lead, in MERGE_PRIORITY order.

    Only keys with a usable value are emitted; ``name_city`` requires a non-empty
    normalised name (city may be ``None``).
    """
    name_norm = getattr(lead, "company_name_norm", None)
    values: dict[str, Any] = {
        "phone_e164": getattr(lead, "phone_e164", None),
        "domain": getattr(lead, "domain", None),
        "name_city": (name_norm, getattr(lead, "city", None)) if name_norm else None,
    }
    return [(key, values[key]) for key in MERGE_PRIORITY if values[key]]
