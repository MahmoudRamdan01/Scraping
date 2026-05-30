from datetime import date

from aol_leadfinder.pipeline.normalize import normalize_lead
from aol_leadfinder.pipeline.score import score_lead
from aol_leadfinder.scrapers.base import RawLead

SCFG = {
    "max_score": 100,
    "tiers": {"Hot": 61, "Medium": 31, "Weak": 0},
    "weights": {
        "has_website": 10,
        "has_phone": 8,
        "has_email": 5,
        "has_linkedin": 5,
        "multiple_branches": 8,
        "has_online_store": 10,
        "in_freight_directory": 10,
    },
    "activity": [{"max_months": 3, "points": 15}, {"max_months": 12, "points": 8}],
    "followers": [{"min": 1000, "points": 15}, {"min": 100, "points": 3}, {"min": 0, "points": 0}],
    "freight_sources": ["freightclub"],
}


def test_hot_lead_scores_high():
    raw = RawLead(
        company_name="Nile Beauty",
        source="egydir",
        phone_raw="01012345678",
        email="info@nile.example",
        website="nile.example",
        social_links={"linkedin": "https://linkedin.com/company/nile"},
        followers=5000,
        last_activity_date=date.today(),
        branches=3,
        has_online_store=True,
    )
    score, tier, breakdown = score_lead(normalize_lead(raw), SCFG)
    assert tier == "Hot"
    assert score >= 61
    factors = {b["factor"] for b in breakdown}
    assert {"has_website", "has_phone", "recent_activity", "followers"} <= factors


def test_weak_lead():
    raw = RawLead(company_name="Tiny", source="egydir", followers=10)
    score, tier, _ = score_lead(normalize_lead(raw), SCFG)
    assert tier == "Weak"
    assert score <= 30


def test_freight_source_intent_points():
    raw = RawLead(company_name="Ship Co", source="freightclub")
    _, _, breakdown = score_lead(normalize_lead(raw), SCFG)
    assert any(b["factor"] == "in_freight_directory" for b in breakdown)


def test_score_clamped_to_max():
    raw = RawLead(
        company_name="Everything",
        source="freightclub",
        phone_raw="01012345678",
        email="a@b.example",
        website="b.example",
        social_links={"linkedin": "x"},
        followers=99999,
        last_activity_date=date.today(),
        branches=10,
        has_online_store=True,
    )
    score, _, _ = score_lead(normalize_lead(raw), SCFG)
    assert score <= SCFG["max_score"]
