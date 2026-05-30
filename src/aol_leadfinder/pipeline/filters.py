"""Quality filters from the sales team's rules (config/filters.yaml).

Returns (passes, reason). ``reason`` is a short machine code when dropped, used
for run statistics so the team can see WHY leads were filtered out.
"""
from __future__ import annotations

from typing import Any, Optional


def passes_filters(lead: Any, fcfg: dict) -> tuple[bool, Optional[str]]:
    if fcfg.get("require_phone") and not getattr(lead, "phone_e164", None):
        return False, "no_phone"

    if fcfg.get("require_website") and not (getattr(lead, "website", None) or getattr(lead, "domain", None)):
        return False, "no_website"

    activity = fcfg.get("activity", {})
    if activity.get("enabled"):
        last = getattr(lead, "last_activity_date", None)
        if last is not None:
            if last.year <= int(activity.get("drop_if_year_at_or_before", 0)):
                return False, "inactive"
        elif activity.get("drop_if_activity_unknown"):
            return False, "activity_unknown"

    followers_cfg = fcfg.get("followers", {})
    if followers_cfg.get("enabled"):
        followers = getattr(lead, "followers", None)
        if followers is not None and followers < int(followers_cfg.get("min", 0)):
            return False, "low_followers"

    return True, None
