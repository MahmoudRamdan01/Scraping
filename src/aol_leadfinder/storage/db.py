"""Database engine + dedup-aware upsert + CRM read/update helpers."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from ..pipeline.dedup import match_keys
from ..pipeline.normalize import NormalizedLead
from .models import QUARANTINE_STATUS, Lead

# Fields merged from a new sighting into an existing lead (fill blanks only).
_MERGE_FIELDS = (
    "phone_e164", "phone_raw", "email", "website", "domain", "address", "city",
    "governorate", "country", "category", "description", "source", "source_url",
    "followers", "last_activity_date", "rating", "branches", "has_online_store",
)
_EMPTY = (None, "", [])

# Columns added after v1 — created on existing DBs via a lightweight migration.
_MIGRATION_COLUMNS = {
    "score_reasons": "JSON",
    "assigned_to": "TEXT",
    "last_contact_date": "DATE",
    "next_followup_date": "DATE",
    "company_type": "TEXT",
    "shipping_intent": "INTEGER",
    "description": "TEXT",
    "target_markets": "JSON",
    "enriched": "INTEGER",
    "sources_seen": "TEXT",
    "quarantine_reason": "TEXT",
}


def _merge_sources_seen(existing_seen: Optional[str], new_source: Optional[str]) -> Optional[str]:
    """Append-only union of source keys, comma-joined and sorted (stable, dedup'd)."""
    seen = {s for s in (existing_seen or "").split(",") if s}
    if new_source:
        seen.add(new_source)
    return ",".join(sorted(seen)) or None

# CRM fields editable from the UI.
_CRM_FIELDS = {"status", "notes", "assigned_to", "last_contact_date", "next_followup_date"}


def get_engine(db_path: Path | str):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):
        # WAL lets the Streamlit UI keep reading while a search run writes
        # (default rollback journal locks them against each other); busy_timeout
        # makes a contended connection wait instead of erroring "database is locked".
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return engine


def _ensure_columns(engine) -> None:
    """Idempotent migration: add CRM/score columns to an existing leads table."""
    insp = inspect(engine)
    if "lead" not in insp.get_table_names():
        return
    existing = {col["name"] for col in insp.get_columns("lead")}
    missing = {c: t for c, t in _MIGRATION_COLUMNS.items() if c not in existing}
    if not missing:
        return
    with engine.begin() as conn:
        for col, coltype in missing.items():
            conn.execute(text(f"ALTER TABLE lead ADD COLUMN {col} {coltype}"))


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_columns(engine)


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


def upsert_lead(
    session: Session,
    n: NormalizedLead,
    run_id: Optional[int] = None,
    *,
    quarantine_reason: Optional[str] = None,
) -> tuple[Lead, bool]:
    """Insert a new lead or merge into an existing one. Returns (lead, created).

    ``quarantine_reason`` (set when the record failed structural validation) only
    takes effect on INSERT: a brand-new broken record is stored as quarantined.
    On MERGE it is intentionally ignored so a broken sighting can never downgrade
    an existing good lead — it merely contributes provenance/blank fields.
    """
    existing = _find_existing(session, n)
    if existing is not None:
        for fld in _MERGE_FIELDS:
            new_val = getattr(n, fld, None)
            if getattr(existing, fld, None) in _EMPTY and new_val not in _EMPTY:
                setattr(existing, fld, new_val)
        # `source` (above) stays the first-seen primary; `sources_seen` accumulates all.
        existing.sources_seen = _merge_sources_seen(existing.sources_seen, n.source)
        extras = set(existing.extra_phones or []) | set(n.extra_phones or [])
        extras.discard(existing.phone_e164)
        existing.extra_phones = sorted(extras) or None
        if n.social_links:
            merged = dict(existing.social_links or {})
            merged.update(n.social_links)
            existing.social_links = merged
        existing.score = n.score
        existing.tier = n.tier
        existing.score_reasons = n.score_reasons or None
        if n.company_type:
            existing.company_type = n.company_type
        if n.shipping_intent is not None:
            existing.shipping_intent = n.shipping_intent
        if n.target_markets:
            existing.target_markets = n.target_markets
        if n.enriched:
            existing.enriched = True
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
        description=n.description,
        source=n.source,
        source_url=n.source_url,
        sources_seen=_merge_sources_seen(None, n.source),
        social_links=(n.social_links or None),
        followers=n.followers,
        last_activity_date=n.last_activity_date,
        rating=n.rating,
        branches=n.branches,
        has_online_store=n.has_online_store,
        company_type=n.company_type,
        shipping_intent=n.shipping_intent,
        target_markets=(n.target_markets or None),
        enriched=n.enriched,
        score=n.score,
        tier=n.tier,
        score_reasons=(n.score_reasons or None),
        status=QUARANTINE_STATUS if quarantine_reason else "new",
        quarantine_reason=quarantine_reason,
        run_id=run_id,
    )
    session.add(lead)
    return lead, True


def read_all_leads(engine, *, include_quarantined: bool = False) -> list[Lead]:
    """Working lead list (highest score first). Quarantined records are excluded
    by default; pass ``include_quarantined=True`` to see everything."""
    with Session(engine) as session:
        stmt = select(Lead)
        if not include_quarantined:
            stmt = stmt.where(Lead.status != QUARANTINE_STATUS)
        return list(session.exec(stmt.order_by(Lead.score.desc())).all())


def read_quarantined(engine) -> list[Lead]:
    """Structurally-invalid records held for review (most recent first)."""
    with Session(engine) as session:
        stmt = select(Lead).where(Lead.status == QUARANTINE_STATUS).order_by(Lead.updated_at.desc())
        return list(session.exec(stmt).all())


def update_lead_crm(engine, lead_id: int, **fields) -> bool:
    """Update CRM fields (status, notes, assigned_to, last/next dates) for a lead."""
    with Session(engine) as session:
        lead = session.get(Lead, lead_id)
        if lead is None:
            return False
        for key, value in fields.items():
            if key in _CRM_FIELDS:
                setattr(lead, key, value)
        lead.updated_at = datetime.utcnow()
        session.add(lead)
        session.commit()
        return True


def update_lead_status(engine, lead_id: int, *, status: Optional[str] = None, notes: Optional[str] = None) -> bool:
    payload = {k: v for k, v in {"status": status, "notes": notes}.items() if v is not None}
    return update_lead_crm(engine, lead_id, **payload)
