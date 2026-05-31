"""Pluggable scraper contract.

Add a new source by subclassing :class:`BaseScraper` with a unique ``key`` and
implementing ``search``. Subclasses auto-register into ``BaseScraper.registry``
when their module is imported (see ``registry.py``), so wiring a new source is:
1. create a module under ``scrapers/green|yellow|deferred/``
2. add an entry to ``config/sources.yaml`` pointing at the module
"""
from __future__ import annotations

import abc
import random
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Iterator, Optional


@dataclass
class SearchRequest:
    country: Optional[str] = None
    governorate: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    max_results: int = 100
    enrich_websites: bool = False


@dataclass
class RawLead:
    """Loose, source-shaped record. The pipeline normalises it before storage."""

    company_name: str
    source: str
    source_url: Optional[str] = None
    phone_raw: Optional[str] = None
    extra_phones: list[str] = field(default_factory=list)
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    governorate: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    social_links: dict = field(default_factory=dict)
    followers: Optional[int] = None
    last_activity_date: Optional[date] = None
    rating: Optional[float] = None
    branches: Optional[int] = None
    has_online_store: Optional[bool] = None
    raw: dict = field(default_factory=dict)


class DeferredScraperDisabled(RuntimeError):
    """Raised when a RED-zone scraper is used without its feature flag enabled."""


class BaseScraper(abc.ABC):
    key: str = ""
    label: str = ""
    tier: str = "green"  # green | yellow | deferred

    registry: dict[str, type["BaseScraper"]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "key", ""):
            BaseScraper.registry[cls.key] = cls

    def __init__(self, meta: Optional[dict] = None):
        self.meta = meta or {}
        rl = self.meta.get("rate_limit", {}) if isinstance(self.meta, dict) else {}
        self.delay_min = float(rl.get("min", 1.5))
        self.delay_max = float(rl.get("max", 4.0))

    def polite_sleep(self) -> None:
        """Human-like pause between requests (zero-budget anti-ban hygiene)."""
        if self.delay_max > 0:
            time.sleep(random.uniform(self.delay_min, self.delay_max))

    @abc.abstractmethod
    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        """Yield RawLeads for the given search request."""
        raise NotImplementedError
