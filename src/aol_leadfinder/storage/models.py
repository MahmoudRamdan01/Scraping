"""SQLModel tables. Single SQLite file at data/leads.db."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

LEAD_STATUSES = ["new", "contacted", "negotiating", "won", "rejected"]


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

    source: Optional[str] = None
    source_url: Optional[str] = None
    social_links: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    followers: Optional[int] = None
    last_activity_date: Optional[date] = None
    rating: Optional[float] = None
    branches: Optional[int] = None
    has_online_store: Optional[bool] = None

    score: int = 0
    tier: str = "Weak"
    status: str = "new"
    notes: Optional[str] = None

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
