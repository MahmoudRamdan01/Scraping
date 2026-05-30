"""Database engine + dedup-aware upsert + simple read/update helpers."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine, select

from ..pipeline.dedup import match_keys
from ..pipeline.normalize import NormalizedLead
from .models import Lead, Run

# Fields merged from a new sighting into an existing lead (fill blanks only).
_MERGE_FIELDS = (
    "phone_e164", "phone_raw", "email", "website", "domain", "address", "city",
    "governorate", "country", "category", "source", "source_url", "followers",
    "last_activity_date", "rating", "branches", "has_online_store",
)
_EMPTY = (None, "", [])


def get_engine(db_path: Path | str):
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)


def _find_existing(session: Session, n: NormalizedLead) -> Optional[Lead]:
    for kind, val in match_keys(n):
        row = None
        if kind == "phone_e164":
            row = session.exec(select(Lead).where(Lead.phone_e164 == val)).first()
        elif kind == "domain":
            row = session.exec(select(Lead).where(Lead.domain == val)).first()
        elif kind == "name_city":
            name_norm, city = val
            stmt = select(Lead).where(Lead.company_name_norm == name_norm)
            stmt = stmt.where(Lead.city == city) if city is not None else stmt.where(Lead.city.is_(None))
            row = session.exec(stmt).first()
        if row:
            return row
    return None


def upsert_lead(session: Session, n: NormalizedLead, run_id: Optional[int] = None) -> tuple[Lead, bool]:
    """Insert a new lead or merge into an existing one. Returns (lead, created)."""
    existing = _find_existing(session, n)
    if existing is not None:
        for fld in _MERGE_FIELDS:
            new_val = getattr(n, fld, None)
            if getattr(existing, fld, None) in _EMPTY and new_val not in _EMPTY:
                setattr(existing, fld, new_val)
        # union secondary phones, never duplicating the primary
        extras = set(existing.extra_phones or []) | set(n.extra_phones or [])
        extras.discard(existing.phone_e164)
        existing.extra_phones = sorted(extras) or None
        if n.social_links:
            merged = dict(existing.social_links or {})
            merged.update(n.social_links)
            existing.social_links = merged
        existing.score = n.score
        existing.tier = n.tier
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        return existing, False

    lead = Lead(
        company_name=n.company_name,
        company_name_norm=n.company_name_norm,
        phone_e164=n.phone_e164,
        phone_raw=n.phone_raw,
        extra_phones=(n.extra_phones or None),
        email=n.email,
        website=n.website,
        domain=n.domain,
        address=n.address,
        city=n.city,
        governorate=n.governorate,
        country=n.country,
        category=n.category,
        source=n.source,
        source_url=n.source_url,
        social_links=(n.social_links or None),
        followers=n.followers,
        last_activity_date=n.last_activity_date,
        rating=n.rating,
        branches=n.branches,
        has_online_store=n.has_online_store,
        score=n.score,
        tier=n.tier,
        status="new",
        run_id=run_id,
    )
    session.add(lead)
    return lead, True


def read_all_leads(engine) -> list[Lead]:
    with Session(engine) as session:
        return list(session.exec(select(Lead).order_by(Lead.score.desc())).all())


def update_lead_status(engine, lead_id: int, *, status: Optional[str] = None, notes: Optional[str] = None) -> bool:
    with Session(engine) as session:
        lead = session.get(Lead, lead_id)
        if lead is None:
            return False
        if status is not None:
            lead.status = status
        if notes is not None:
            lead.notes = notes
        lead.updated_at = datetime.utcnow()
        session.add(lead)
        session.commit()
        return True
