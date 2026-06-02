"""SQLModel tables. Single SQLite file at data/leads.db."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

# CRM pipeline stages (machine values).
LEAD_STATUSES = [
    "new",
    "contacted",
    "interested",
    "quotation_sent",
    "negotiation",
    "won",
    "lost",
]

# Arabic labels for the UI (machine value -> label).
STATUS_LABELS_AR = {
    "new": "جديد",
    "contacted": "تم التواصل",
    "interested": "مهتم",
    "quotation_sent": "اتبعت عرض سعر",
    "negotiation": "تفاوض",
    "won": "تعاقد ✅",
    "lost": "خسارة",
}

# Statuses that count as "engaged" when computing conversion rate.
ENGAGED_STATUSES = ["contacted", "interested", "quotation_sent", "negotiation", "won"]

# Sentinel status for structurally-invalid records: kept for review but excluded
# from the working lead list and conversion math. Intentionally NOT part of
# LEAD_STATUSES (the sales pipeline) so it never pollutes funnel metrics.
QUARANTINE_STATUS = "quarantined"


class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    company_name: str
    company_name_norm: str = Field(index=True)

    phone_e164: Optional[str] = Field(default=None, index=True)
    phone_raw: Optional[str] = None
    extra_phones: Optional[list] = Field(default=None, sa_column=Column(JSON))

    email: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = Field(default=None, index=True)

    address: Optional[str] = None
    city: Optional[str] = None
    governorate: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None

    source: Optional[str] = None  # primary (first-seen) source
    source_url: Optional[str] = None
    sources_seen: Optional[str] = None  # comma-joined union of every source that contributed
    social_links: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    followers: Optional[int] = None
    last_activity_date: Optional[date] = None
    rating: Optional[float] = None
    branches: Optional[int] = None
    has_online_store: Optional[bool] = None

    company_type: Optional[str] = None
    shipping_intent: Optional[int] = None
    target_markets: Optional[list] = Field(default=None, sa_column=Column(JSON))
    enriched: bool = False

    score: int = 0
    tier: str = "Weak"
    score_reasons: Optional[list] = Field(default=None, sa_column=Column(JSON))

    # ---- CRM fields ----
    status: str = "new"
    quarantine_reason: Optional[str] = None  # set only when status == QUARANTINE_STATUS
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    last_contact_date: Optional[date] = None
    next_followup_date: Optional[date] = None

    run_id: Optional[int] = Field(default=None, foreign_key="run.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    params: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    found: int = 0
    kept: int = 0
    dropped: int = 0
    created: int = 0
    updated: int = 0
    status: str = "running"
    error: Optional[str] = None
