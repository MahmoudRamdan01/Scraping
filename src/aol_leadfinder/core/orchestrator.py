"""End-to-end search run: scrape -> normalize -> dedup/upsert -> filter -> score -> persist.

One failing source never aborts the whole run; its error is recorded and the
other sources continue.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlmodel import Session

from ..config import Settings, get_filters, get_scoring, get_settings
from ..logging_setup import get_logger
from ..pipeline.filters import passes_filters
from ..pipeline.normalize import normalize_lead
from ..pipeline.score import score_lead
from ..scrapers import registry
from ..scrapers.base import SearchRequest
from ..storage.db import get_engine, init_db, upsert_lead
from ..storage.models import Run

log = get_logger("orchestrator")


@dataclass
class RunStats:
    found: int = 0
    kept: int = 0
    dropped: int = 0
    created: int = 0
    updated: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    run_id: Optional[int] = None

    def drop(self, reason: Optional[str]) -> None:
        self.dropped += 1
        key = reason or "unknown"
        self.drop_reasons[key] = self.drop_reasons.get(key, 0) + 1


def run_search(req: SearchRequest, source_keys: list[str], *, settings: Optional[Settings] = None) -> RunStats:
    settings = settings or get_settings()
    scoring = get_scoring()
    filters = get_filters()

    engine = get_engine(settings.db_path)
    init_db(engine)
    scrapers = registry.instantiate(source_keys)

    stats = RunStats()
    with Session(engine) as session:
        run = Run(
            params={
                "sources": list(scrapers.keys()),
                "country": req.country,
                "governorate": req.governorate,
                "city": req.city,
                "category": req.category,
                "max_results": req.max_results,
            },
            status="running",
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        stats.run_id = run.id

        for key, scraper in scrapers.items():
            try:
                for raw in itertools.islice(scraper.search(req), req.max_results):
                    stats.found += 1
                    norm = normalize_lead(
                        raw, default_country=settings.default_country, region=settings.default_region
                    )
                    ok, reason = passes_filters(norm, filters)
                    if not ok:
                        stats.drop(reason)
                        continue
                    score, tier, reasons = score_lead(norm, scoring)
                    norm.score, norm.tier, norm.score_reasons = score, tier, reasons
                    _, created = upsert_lead(session, norm, run.id)
                    stats.kept += 1
                    stats.created += int(created)
                    stats.updated += int(not created)
                session.commit()
            except Exception as exc:  # noqa: BLE001 - isolate per-source failures
                log.exception("source '%s' failed", key)
                stats.errors[key] = str(exc)
                session.rollback()

        run.found = stats.found
        run.kept = stats.kept
        run.dropped = stats.dropped
        run.created = stats.created
        run.updated = stats.updated
        run.status = "done_with_errors" if stats.errors else "done"
        run.error = "; ".join(f"{k}: {v}" for k, v in stats.errors.items()) or None
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()

    return stats
