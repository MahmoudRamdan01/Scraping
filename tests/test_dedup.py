from sqlmodel import Session

from aol_leadfinder.pipeline.normalize import normalize_lead
from aol_leadfinder.scrapers.base import RawLead
from aol_leadfinder.storage.db import get_engine, init_db, read_all_leads, upsert_lead


def _engine():
    engine = get_engine(":memory:")
    init_db(engine)
    return engine


def test_upsert_dedupes_by_phone_and_merges():
    engine = _engine()
    with Session(engine) as session:
        a = normalize_lead(RawLead(company_name="Nile Beauty", source="egydir", phone_raw="01012345678"))
        lead1, created1 = upsert_lead(session, a)
        session.commit()
        assert created1 is True

        # Same phone, new info (website + email) -> should MERGE, not duplicate
        b = normalize_lead(
            RawLead(
                company_name="Nile Beauty Cosmetics",
                source="egydir",
                phone_raw="+20 101 234 5678",
                website="nile.example",
                email="info@nile.example",
            )
        )
        lead2, created2 = upsert_lead(session, b)
        session.commit()
        assert created2 is False
        assert lead2.id == lead1.id

    leads = read_all_leads(engine)
    assert len(leads) == 1
    assert leads[0].domain == "nile.example"
    assert leads[0].email == "info@nile.example"


def test_upsert_dedupes_by_domain():
    engine = _engine()
    with Session(engine) as session:
        a = normalize_lead(RawLead(company_name="Alpha", source="egydir", website="acme.example"))
        upsert_lead(session, a)
        session.commit()
        b = normalize_lead(RawLead(company_name="Alpha Co", source="kompass_eg", website="https://acme.example/contact"))
        _, created = upsert_lead(session, b)
        session.commit()
        assert created is False

    assert len(read_all_leads(engine)) == 1


def test_distinct_leads_are_kept_separate():
    engine = _engine()
    with Session(engine) as session:
        upsert_lead(session, normalize_lead(RawLead(company_name="One", source="egydir", phone_raw="01012345678")))
        upsert_lead(session, normalize_lead(RawLead(company_name="Two", source="egydir", phone_raw="01087654321")))
        session.commit()
    assert len(read_all_leads(engine)) == 2
