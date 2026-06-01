"""Merge policy: explicit priority, exact name+city only, no fuzzy.

The dangerous case this guards is a *false merge* — two genuinely different
companies collapsed into one. Exact normalised name+city must merge; the same
name in a different city must stay separate.
"""
from sqlmodel import Session

from aol_leadfinder.pipeline.dedup import MERGE_PRIORITY, match_keys
from aol_leadfinder.pipeline.normalize import normalize_lead
from aol_leadfinder.scrapers.base import RawLead
from aol_leadfinder.storage.db import get_engine, init_db, read_all_leads, upsert_lead


def _engine():
    engine = get_engine(":memory:")
    init_db(engine)
    return engine


def test_merge_priority_is_explicit_and_ordered():
    assert MERGE_PRIORITY == ("phone_e164", "domain", "name_city")


def test_match_keys_emits_present_keys_in_priority_order():
    full = normalize_lead(
        RawLead(company_name="Acme", source="egydir", phone_raw="01012345678", website="acme.example")
    )
    assert [k for k, _ in match_keys(full)] == ["phone_e164", "domain", "name_city"]

    # A name-only record emits just the weakest key.
    bare = normalize_lead(RawLead(company_name="Acme", source="egydir", city="Cairo"))
    assert [k for k, _ in match_keys(bare)] == ["name_city"]


def test_same_name_and_city_merges_without_phone_or_domain():
    engine = _engine()
    with Session(engine) as session:
        upsert_lead(session, normalize_lead(RawLead(company_name="Nile Foods", source="egydir", city="Cairo")))
        _, created = upsert_lead(
            session, normalize_lead(RawLead(company_name="Nile Foods", source="yellowpages_eg", city="Cairo"))
        )
        session.commit()
        assert created is False
    assert len(read_all_leads(engine)) == 1


def test_same_name_different_city_stays_separate():
    engine = _engine()
    with Session(engine) as session:
        upsert_lead(session, normalize_lead(RawLead(company_name="Royal Pharma", source="egydir", city="Cairo")))
        _, created = upsert_lead(
            session, normalize_lead(RawLead(company_name="Royal Pharma", source="egydir", city="Alexandria"))
        )
        session.commit()
        assert created is True  # different city -> distinct company, no false merge
    assert len(read_all_leads(engine)) == 2


def test_sources_seen_accumulates_while_primary_source_is_stable():
    engine = _engine()
    with Session(engine) as session:
        # Same phone seen by three sources -> one lead, provenance preserved.
        for src in ("google_maps", "egydir", "yellowpages_eg"):
            upsert_lead(session, normalize_lead(RawLead(company_name="Cairo Textiles", source=src, phone_raw="01012345678")))
        session.commit()
    leads = read_all_leads(engine)
    assert len(leads) == 1
    assert leads[0].source == "google_maps"  # primary = first seen, never overwritten
    assert leads[0].sources_seen == "egydir,google_maps,yellowpages_eg"  # sorted union of all

