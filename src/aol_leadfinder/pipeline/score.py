"""Transparent, config-driven lead scoring (config/scoring.yaml).

Two engines share one entry point ``score_lead`` and one output contract
``(score, tier, breakdown)`` where breakdown is a list of {"factor", "points"}:

* **Band engine** (when ``scoring.yaml`` defines ``base_bands``): the score starts
  from a base band chosen by the company's *business fit* (a factory/product-maker
  outranks a trader outranks general-trading; services and competitors are floored
  /capped), then reachability bonuses (website, online store, ships, phone, …) push
  it up to ``max_score``. This is what makes leads actually separate into tiers and
  encodes the sales team's 100/70/50/20 rule.
* **Legacy additive engine** (when there is no ``base_bands``): the original
  presence-based points. Kept so callers passing a bare weights config (e.g. unit
  tests) get the exact previous behaviour.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional


def _months_since(d: date) -> int:
    today = date.today()
    return (today.year - d.year) * 12 + (today.month - d.month)


def _tier_for(score: int, tiers: dict) -> str:
    best_name, best_threshold = "Weak", -1
    for name, threshold in tiers.items():
        if score >= threshold and threshold >= best_threshold:
            best_name, best_threshold = name, threshold
    return best_name


def score_lead(lead: Any, scfg: dict, *, segments: Optional[dict] = None) -> tuple[int, str, list[dict]]:
    if scfg.get("base_bands"):
        return _band_score(lead, scfg, segments or {})
    return _legacy_score(lead, scfg)


# ---------------------------------------------------------------------------
# Band engine (business-fit first, anchored to the 100/70/50/20 rule)
# ---------------------------------------------------------------------------

_DEFAULT_BANDS = {
    "product_maker": 62,    # Manufacturer / Exporter — base; bonuses push toward 100
    "trader": 52,           # Importer / Distributor — the "70" band
    "ecommerce": 60,        # online sellers ship constantly
    "general_trading": 38,  # generic Import & Export — the "50" band
    "service": 20,          # floored (the "20" band)
    "competitor": 10,       # freight forwarders — never a real lead
    "default": 32,
}
_DEFAULT_BONUSES = {
    "has_website": 10,
    "has_online_store": 12,
    "ships": 8,
    "has_phone": 6,
    "has_email": 5,
    "has_contact_person": 6,
    "has_linkedin": 4,
}
_DEFAULT_TIERS = {"Hot": 65, "Medium": 40, "Weak": 0}
_PRODUCT_MAKER_TYPES = ("Manufacturer", "Exporter")
_TRADER_TYPES = ("Importer", "Distributor")


def _band_key(lead: Any, segment: Optional[str]) -> str:
    if segment == "competitor" or getattr(lead, "is_competitor", False):
        return "competitor"
    if segment == "service":
        return "service"
    ctype = getattr(lead, "company_type", None) or ""
    if ctype in _PRODUCT_MAKER_TYPES:
        return "product_maker"
    if ctype in _TRADER_TYPES:
        return "trader"
    if ctype == "Ecommerce":
        return "ecommerce"
    # Untyped but in-target leads still get a sensible band from their segment.
    if segment == "P1":
        return "trader"
    if segment == "P2":
        return "ecommerce"
    if segment == "P3":
        return "general_trading"
    cat = (getattr(lead, "category", None) or "").lower()
    if "import" in cat and "export" in cat:
        return "general_trading"
    return "default"


def _ships(lead: Any) -> bool:
    markets = getattr(lead, "target_markets", None) or []
    if any(not str(m).startswith("Local") for m in markets):
        return True
    intent = getattr(lead, "shipping_intent", None) or 0
    return int(intent) >= 40


def _band_score(lead: Any, scfg: dict, segments: dict) -> tuple[int, str, list[dict]]:
    bands = {**_DEFAULT_BANDS, **scfg.get("base_bands", {})}
    bonuses = {**_DEFAULT_BONUSES, **scfg.get("bonuses", {})}
    tiers = scfg.get("tiers", _DEFAULT_TIERS)
    max_score = int(scfg.get("max_score", 100))

    segment = getattr(lead, "segment", None)
    key = _band_key(lead, segment)
    breakdown: list[dict] = [{"factor": f"band:{key}", "points": int(bands.get(key, bands["default"]))}]
    total = int(bands.get(key, bands["default"]))

    # Services and competitors are intentionally flat (floored/capped): a polished
    # website must not turn a forwarder or a marketing agency into a hot lead.
    if key in ("service", "competitor"):
        tier = _tier_for(total, tiers)
        return min(total, max_score), tier, breakdown

    def add(factor: str, points: int) -> None:
        nonlocal total
        if points:
            total += points
            breakdown.append({"factor": factor, "points": points})

    if getattr(lead, "website", None) or getattr(lead, "domain", None):
        add("has_website", bonuses.get("has_website", 0))
    if getattr(lead, "has_online_store", None):
        add("has_online_store", bonuses.get("has_online_store", 0))
    if _ships(lead):
        add("ships", bonuses.get("ships", 0))
    if getattr(lead, "phone_e164", None):
        add("has_phone", bonuses.get("has_phone", 0))
    if getattr(lead, "email", None):
        add("has_email", bonuses.get("has_email", 0))
    if getattr(lead, "contact_name", None) or getattr(lead, "contact_role", None):
        add("has_contact_person", bonuses.get("has_contact_person", 0))
    social = getattr(lead, "social_links", None) or {}
    if getattr(lead, "linkedin", None) or social.get("linkedin"):
        add("has_linkedin", bonuses.get("has_linkedin", 0))

    total = min(total, max_score)
    return total, _tier_for(total, tiers), breakdown


# ---------------------------------------------------------------------------
# Legacy additive engine (unchanged behaviour for bare weights configs)
# ---------------------------------------------------------------------------


def _legacy_score(lead: Any, scfg: dict) -> tuple[int, str, list[dict]]:
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

    intent = getattr(lead, "shipping_intent", None)
    if intent:
        add("shipping_intent", min(int(intent) // 5, int(scfg.get("max_intent_points", 20))))

    total = min(total, int(scfg.get("max_score", 100)))
    tier = _tier_for(total, scfg.get("tiers", {"Hot": 61, "Medium": 31, "Weak": 0}))
    return total, tier, breakdown


# Human-readable labels for the "Why this lead?" explainability feature.
REASON_LABELS = {
    "has_website": "موقع ✓",
    "has_phone": "رقم ✓",
    "has_email": "إيميل ✓",
    "has_linkedin": "LinkedIn ✓",
    "has_contact_person": "مسؤول تواصل ✓",
    "has_online_store": "متجر إلكتروني ✓",
    "ships": "بيشحن ✓",
    "multiple_branches": "فروع متعددة ✓",
    "in_freight_directory": "شركة شحن ✓",
    "recent_activity": "نشاط حديث ✓",
    "followers": "متابعين كفاية ✓",
    "shipping_intent": "نية شحن ✓",
    "band:product_maker": "مصنع/منتج ✓",
    "band:trader": "مستورد/موزّع ✓",
    "band:ecommerce": "متجر إلكتروني ✓",
    "band:general_trading": "تجارة عامة",
    "band:service": "شركة خدمات",
    "band:competitor": "منافس (شحن)",
    "band:default": "غير مصنّف",
}


def format_reasons(reasons) -> str:
    """Human-readable 'why this lead' string from a score breakdown list."""
    if not reasons:
        return ""
    return "، ".join(REASON_LABELS.get(r.get("factor"), r.get("factor", "")) for r in reasons)
