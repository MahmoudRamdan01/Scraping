"""Transparent, config-driven lead scoring (config/scoring.yaml).

Returns (score, tier, breakdown) where breakdown is a list of
{"factor", "points"} so the UI can explain *why* a lead got its score.
"""
from __future__ import annotations

from datetime import date
from typing import Any


def _months_since(d: date) -> int:
    today = date.today()
    return (today.year - d.year) * 12 + (today.month - d.month)


def _tier_for(score: int, tiers: dict) -> str:
    best_name, best_threshold = "Weak", -1
    for name, threshold in tiers.items():
        if score >= threshold and threshold >= best_threshold:
            best_name, best_threshold = name, threshold
    return best_name


def score_lead(lead: Any, scfg: dict) -> tuple[int, str, list[dict]]:
    weights = scfg.get("weights", {})
    total = 0
    breakdown: list[dict] = []

    def add(factor: str, points: int) -> None:
        nonlocal total
        if points:
            total += points
            breakdown.append({"factor": factor, "points": points})

    if getattr(lead, "website", None) or getattr(lead, "domain", None):
        add("has_website", weights.get("has_website", 0))
    if getattr(lead, "phone_e164", None):
        add("has_phone", weights.get("has_phone", 0))
    if getattr(lead, "email", None):
        add("has_email", weights.get("has_email", 0))
    social = getattr(lead, "social_links", None) or {}
    if social.get("linkedin"):
        add("has_linkedin", weights.get("has_linkedin", 0))
    branches = getattr(lead, "branches", None)
    if branches and branches > 1:
        add("multiple_branches", weights.get("multiple_branches", 0))
    if getattr(lead, "has_online_store", None):
        add("has_online_store", weights.get("has_online_store", 0))

    freight_sources = set(scfg.get("freight_sources", []))
    category = (getattr(lead, "category", None) or "").lower()
    is_freight = getattr(lead, "source", None) in freight_sources or (
        "freight" in category or "forwarder" in category
    )
    if is_freight:
        add("in_freight_directory", weights.get("in_freight_directory", 0))

    last = getattr(lead, "last_activity_date", None)
    if last is not None:
        months = _months_since(last)
        for bucket in scfg.get("activity", []):
            if months <= bucket["max_months"]:
                add("recent_activity", bucket["points"])
                break

    followers = getattr(lead, "followers", None)
    if followers is not None:
        for bucket in scfg.get("followers", []):
            if followers >= bucket["min"]:
                add("followers", bucket["points"])
                break

    total = min(total, int(scfg.get("max_score", 100)))
    tier = _tier_for(total, scfg.get("tiers", {"Hot": 61, "Medium": 31, "Weak": 0}))
    return total, tier, breakdown
