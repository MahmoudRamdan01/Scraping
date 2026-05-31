import datetime as dt

from sqlalchemy import inspect, text
from sqlmodel import Session

from aol_leadfinder.pipeline.normalize import normalize_lead
from aol_leadfinder.scrapers.base import RawLead
from aol_leadfinder.storage.db import (
    _ensure_columns,
    get_engine,
    init_db,
    read_all_leads,
    update_lead_crm,
    upsert_lead,
)


def test_ensure_columns_migrates_old_schema():
    """An old leads table (pre-CRM) gets the new columns added idempotently."""
    engine = get_engine(":memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE lead (id INTEGER PRIMARY KEY, "
                "company_name TEXT, company_name_norm TEXT)"
            )
        )
    _ensure_columns(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("lead")}
    assert {
        "score_reasons", "assigned_to", "last_contact_date", "next_followup_date",
        "company_type", "shipping_intent",
    } <= cols
    # Idempotent: running again is a no-op (no error)
    _ensure_columns(engine)


def test_update_lead_crm_persists_fields():
    engine = get_engine(":memory:")
    init_db(engine)
    with Session(engine) as session:
        lead, _ = upsert_lead(
            session, normalize_lead(RawLead(company_name="Ship Co", source="freightclub", phone_raw="01012345678"))
        )
        session.commit()
        lead_id = lead.id

    ok = update_lead_crm(
        engine,
        lead_id,
        status="quotation_sent",
        assigned_to="Sara",
        last_contact_date=dt.date(2026, 5, 30),
        next_followup_date=dt.date(2026, 6, 2),
        notes="sent local price list",
    )
    assert ok is True

    lead = read_all_leads(engine)[0]
    assert lead.status == "quotation_sent"
    assert lead.assigned_to == "Sara"
    assert lead.last_contact_date == dt.date(2026, 5, 30)
    assert lead.next_followup_date == dt.date(2026, 6, 2)
    assert lead.notes == "sent local price list"


def test_score_reasons_persisted():
    engine = get_engine(":memory:")
    init_db(engine)
    with Session(engine) as session:
        norm = normalize_lead(RawLead(company_name="X", source="freightclub", phone_raw="01012345678", website="x.example"))
        norm.score = 50
        norm.tier = "Medium"
        norm.score_reasons = [{"factor": "has_website", "points": 10}]
        upsert_lead(session, norm)
        session.commit()
    lead = read_all_leads(engine)[0]
    assert lead.score_reasons == [{"factor": "has_website", "points": 10}]
