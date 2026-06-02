"""Quarantine behaviour: broken data is kept-but-flagged, never silently dropped,
and never downgrades an existing good lead."""
from sqlmodel import Session

from aol_leadfinder.pipeline.normalize import normalize_lead
from aol_leadfinder.scrapers.base import RawLead
from aol_leadfinder.storage.db import (
    get_engine,
    init_db,
    read_all_leads,
    read_quarantined,
    upsert_lead,
)
from aol_leadfinder.storage.models import QUARANTINE_STATUS


def _engine():
    engine = get_engine(":memory:")
    init_db(engine)
    return engine


def test_quarantined_lead_stored_but_excluded_from_working_list():
    engine = _engine()
    with Session(engine) as session:
        n = normalize_lead(RawLead(company_name="No Contact Co", source="egydir"))
        lead, created = upsert_lead(session, n, quarantine_reason="no_contact")
        session.commit()
        assert created is True
        assert lead.status == QUARANTINE_STATUS
        assert lead.quarantine_reason == "no_contact"

    assert read_all_leads(engine) == []  # excluded from the working list
    assert len(read_all_leads(engine, include_quarantined=True)) == 1
    held = read_quarantined(engine)
    assert len(held) == 1 and held[0].quarantine_reason == "no_contact"


def test_broken_sighting_does_not_downgrade_existing_good_lead():
    engine = _engine()
    with Session(engine) as session:
        good = normalize_lead(
            RawLead(company_name="Acme", source="egydir", phone_raw="01012345678", city="Cairo")
        )
        upsert_lead(session, good)  # valid -> status "new"
        session.commit()

        # A later broken (no-contact) sighting that matches by name+city.
        broken = normalize_lead(RawLead(company_name="Acme", source="yellowpages_eg", city="Cairo"))
        lead, created = upsert_lead(session, broken, quarantine_reason="no_contact")
        session.commit()
        assert created is False  # merged into the good lead
        assert lead.status == "new"  # NOT downgraded
        assert lead.quarantine_reason is None

    assert len(read_all_leads(engine)) == 1  # still in the working list
    assert read_quarantined(engine) == []
