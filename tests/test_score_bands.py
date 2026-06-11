"""Band scoring — the sales team's 100/70/50/20 rule, against the shipped config.

These exercise the *band* engine (config has base_bands). The legacy additive
engine stays covered by test_score.py (its inline config has no base_bands).
"""
from aol_leadfinder.config import get_scoring
from aol_leadfinder.pipeline.normalize import NormalizedLead
from aol_leadfinder.pipeline.score import score_lead

SCFG = get_scoring()


def _lead(**kw):
    return NormalizedLead(company_name="X", company_name_norm="x", source=kw.pop("source", "s"), **kw)


def test_qualified_factory_scores_near_100_hot():
    lead = _lead(
        company_type="Manufacturer", segment="P1",
        website="https://factory.example", has_online_store=True,
        target_markets=["GCC", "Europe"], phone_e164="+201001234567",
        email="sales@factory.example", contact_role="Export Manager",
        linkedin="https://linkedin.com/company/factory",
    )
    score, tier, _ = score_lead(lead, SCFG)
    assert score >= 90
    assert tier == "Hot"


def test_importer_lands_in_the_70_band():
    lead = _lead(company_type="Importer", segment="P1", website="https://imp.example", phone_e164="+201001234567")
    score, tier, _ = score_lead(lead, SCFG)
    assert 60 <= score <= 80
    assert tier == "Hot"


def test_general_trading_is_medium():
    lead = _lead(category="Import & Export", segment="P3", website="https://t.example", phone_e164="+201001234567")
    score, tier, _ = score_lead(lead, SCFG)
    assert 45 <= score <= 60
    assert tier == "Medium"


def test_service_is_floored_to_20_weak():
    # Even with a website + phone, a service company stays flat at the floor.
    lead = _lead(segment="service", website="https://agency.example", phone_e164="+201001234567")
    score, tier, _ = score_lead(lead, SCFG)
    assert score == 20
    assert tier == "Weak"


def test_competitor_is_capped_low():
    lead = _lead(
        company_type="Freight Forwarder", is_competitor=True, segment="competitor",
        website="https://forwarder.example", phone_e164="+201001234567", has_online_store=True,
    )
    score, tier, _ = score_lead(lead, SCFG)
    assert score <= 20
    assert tier == "Weak"


def test_bands_separate_tiers():
    # The whole point: a qualified maker and a service company land in different tiers.
    maker = score_lead(_lead(company_type="Manufacturer", segment="P1", website="https://m.example",
                             phone_e164="+201001234567", has_online_store=True, target_markets=["GCC"]), SCFG)[0]
    service = score_lead(_lead(segment="service"), SCFG)[0]
    assert maker - service >= 40
