"""End-to-end search run: scrape -> normalize -> dedup/upsert -> filter -> score -> persist.

One failing source never aborts the whole run; its error is recorded and the
other sources continue.
"""
from __future__ import annotations

import itertools
import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlmodel import Session

from ..config import Settings, get_filters, get_scoring, get_segments, get_settings
from ..enrichment.crawler import crawl_website
from ..enrichment.intelligence import classify_company
from ..logging_setup import get_logger
from ..pipeline.filters import passes_filters
from ..pipeline.normalize import normalize_lead
from ..pipeline.score import score_lead
from ..pipeline.segment import classify_segment
from ..pipeline.validate import validate_lead
from ..scrapers import registry
from ..scrapers.base import SearchRequest
from ..storage.db import get_engine, init_db, upsert_lead
from ..storage.models import Run

log = get_logger("orchestrator")

# Error-message fragments that indicate a source was actively blocked rather than
# generically crashing. Best-effort: a source is only classified "blocked" when it
# lets such an error propagate. A source that swallows a block and yields nothing
# is reported as "empty" — still the actionable signal (see SourceStat.health).
_BLOCK_SIGNALS = (
    "403", "429", "forbidden", "captcha", "cloudflare",
    "blocked", "access denied", "too many requests",
)


def _looks_blocked(error: Optional[str]) -> bool:
    low = (error or "").lower()
    return any(sig in low for sig in _BLOCK_SIGNALS)


@dataclass
class SourceStat:
    """Per-source outcome for a single run (Sprint A observability)."""

    found: int = 0
    kept: int = 0
    dropped: int = 0
    quarantined: int = 0
    error: Optional[str] = None

    @property
    def health(self) -> str:
        """ok = produced leads · empty = ran but nothing · blocked/error = raised."""
        if self.error:
            return "blocked" if _looks_blocked(self.error) else "error"
        return "ok" if self.found > 0 else "empty"

    def as_dict(self) -> dict:
        return {
            "found": self.found,
            "kept": self.kept,
            "dropped": self.dropped,
            "quarantined": self.quarantined,
            "errors": 1 if self.error else 0,
            "error": self.error,
            "health": self.health,
        }


@dataclass
class RunStats:
    found: int = 0
    kept: int = 0
    dropped: int = 0
    quarantined: int = 0
    created: int = 0
    updated: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    quarantine_reasons: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    per_source: dict[str, SourceStat] = field(default_factory=dict)
    run_id: Optional[int] = None

    def source(self, key: str) -> SourceStat:
        return self.per_source.setdefault(key, SourceStat())

    def drop(self, reason: Optional[str]) -> None:
        self.dropped += 1
        key = reason or "unknown"
        self.drop_reasons[key] = self.drop_reasons.get(key, 0) + 1

    def quarantine(self, reason: Optional[str]) -> None:
        self.quarantined += 1
        key = reason or "unknown"
        self.quarantine_reasons[key] = self.quarantine_reasons.get(key, 0) + 1


def _enrich_website(norm, region: str = "EG") -> None:
    """Crawl the lead's website (Contact/About/Services) and attach intelligence.

    Phones from the website are trusted over a directory-supplied number, because
    directories frequently carry stale/wrong numbers while the company's own site
    is authoritative. All valid numbers are kept (primary + extra_phones), and
    WhatsApp-reachable numbers are recorded in social_links.
    """
    intel = crawl_website(norm.website, category=norm.category, region=region)
    if intel.pages_crawled == 0:
        return
    norm.enriched = True
    if (not norm.company_type or norm.company_type == "Unknown") and intel.company_type != "Unknown":
        norm.company_type = intel.company_type
    if intel.shipping_intent:
        norm.shipping_intent = max(norm.shipping_intent or 0, intel.shipping_intent)
    if intel.has_online_store:
        norm.has_online_store = True
    if intel.store_platform and not norm.store_platform:
        norm.store_platform = intel.store_platform
    if intel.markets:
        norm.target_markets = intel.markets
    if not norm.email and intel.emails:
        norm.email = intel.emails[0]
    # Discovery channels + decision-maker contact (fill-if-blank).
    if intel.facebook and not norm.facebook:
        norm.facebook = intel.facebook
    if intel.linkedin and not norm.linkedin:
        norm.linkedin = intel.linkedin
        links = dict(norm.social_links or {})
        links.setdefault("linkedin", intel.linkedin)
        norm.social_links = links
    if intel.contact_role and not norm.contact_role:
        norm.contact_name = intel.contact_name
        norm.contact_role = intel.contact_role
        norm.contact_email = intel.contact_email or norm.contact_email

    # Phones: website is authoritative. Merge directory + website, keep all valid.
    site_phones = intel.phones  # already validated E.164, contact-page first
    if site_phones:
        # Prefer a WhatsApp-reachable number as primary when available.
        primary = next((p for p in site_phones if p in intel.whatsapp), site_phones[0])
        all_phones = []
        for p in [primary, norm.phone_e164, *site_phones]:
            if p and p not in all_phones:
                all_phones.append(p)
        norm.phone_e164 = all_phones[0]
        norm.phone_raw = norm.phone_raw or all_phones[0]
        extras = [p for p in all_phones[1:] if p != norm.phone_e164]
        merged_extras = list(norm.extra_phones or [])
        for p in extras:
            if p not in merged_extras:
                merged_extras.append(p)
        norm.extra_phones = merged_extras or None

    if intel.whatsapp:
        links = dict(norm.social_links or {})
        links["whatsapp"] = "https://wa.me/" + intel.whatsapp[0].lstrip("+")
        norm.social_links = links


@dataclass
class ProcessedLead:
    """Outcome of the pure (DB-free) per-lead pipeline. The caller does the
    upsert/stats so this function can run in a worker thread with no DB access."""

    norm: object
    outcome: str  # "keep" | "drop" | "quarantine"
    reason: Optional[str] = None
    created: Optional[bool] = None  # filled by the DB writer for "keep"


def _process_raw(
    raw, *, settings: Settings, scoring: dict, filters: dict, segments: dict, enrich: bool
) -> ProcessedLead:
    """normalize -> classify -> (optional) enrich -> validate -> filter -> segment -> score.

    Pure: no database, no shared state. Returns the decision; the single DB writer
    applies it. The sequential and concurrent paths both call this, so their
    semantics can never drift.
    """
    norm = normalize_lead(raw, default_country=settings.default_country, region=settings.default_region)
    # Company Intelligence from the listing description (offline, free).
    # Falls back to the category when there's no description text.
    if norm.description or norm.category:
        intel = classify_company(norm.description or "", norm.category)
        norm.company_type = intel.company_type
        norm.shipping_intent = intel.shipping_intent
        norm.is_competitor = intel.is_competitor
        if intel.has_online_store:
            norm.has_online_store = True
    # Optional deep website crawl (fills phone/email/type/intent/socials/contacts).
    if enrich and norm.website:
        _enrich_website(norm, settings.default_region)
    norm.is_competitor = norm.is_competitor or (norm.company_type == "Freight Forwarder")
    if not norm.product_type and norm.category:
        norm.product_type = norm.category  # the searched category is the product type
    # Structural validation BEFORE quality filters: broken data (no identity /
    # no contact / bad phone) is quarantined — kept for review, excluded from the
    # working list — never silently dropped and never allowed to pollute real leads.
    valid, vreason = validate_lead(norm)
    if not valid:
        return ProcessedLead(norm=norm, outcome="quarantine", reason=vreason)
    ok, reason = passes_filters(norm, filters)
    if not ok:
        return ProcessedLead(norm=norm, outcome="drop", reason=reason)
    norm.segment = classify_segment(norm, segments)
    score, tier, reasons = score_lead(norm, scoring, segments=segments)
    norm.score, norm.tier, norm.score_reasons = score, tier, reasons
    return ProcessedLead(norm=norm, outcome="keep")


def _apply_processed(session: Session, processed: ProcessedLead, run_id: Optional[int],
                     stats: RunStats, ss: SourceStat) -> None:
    """Persist one processed lead and update counters. Single-writer side."""
    norm = processed.norm
    if processed.outcome == "quarantine":
        upsert_lead(session, norm, run_id, quarantine_reason=processed.reason)
        stats.quarantine(processed.reason)
        ss.quarantined += 1
    elif processed.outcome == "drop":
        stats.drop(processed.reason)
        ss.dropped += 1
    else:  # keep
        _, created = upsert_lead(session, norm, run_id)
        stats.kept += 1
        ss.kept += 1
        stats.created += int(created)
        stats.updated += int(not created)


def _run_sequential(req, scrapers, session, run_id, stats, settings, scoring, filters, segments) -> None:
    """The original, deterministic path: one source at a time, commit per source.
    Used whenever max_workers <= 1 (all unit tests), so its behaviour is unchanged."""
    for key, scraper in scrapers.items():
        ss = stats.source(key)
        try:
            for raw in itertools.islice(scraper.search(req), req.max_results):
                stats.found += 1
                ss.found += 1
                processed = _process_raw(
                    raw, settings=settings, scoring=scoring, filters=filters,
                    segments=segments, enrich=req.enrich_websites,
                )
                _apply_processed(session, processed, run_id, stats, ss)
            session.commit()
        except Exception as exc:  # noqa: BLE001 - isolate per-source failures
            log.exception("source '%s' failed", key)
            stats.errors[key] = str(exc)
            ss.error = str(exc)
            session.rollback()


_QUEUE_SENTINEL = object()


def _run_concurrent(req, scrapers, session, run_id, stats, settings, scoring, filters, segments, max_workers) -> None:
    """Producer/consumer: scraper threads do scrape+normalize+enrich (no DB) and
    push results onto a queue; THIS (main) thread is the sole DB writer, so SQLite
    never sees concurrent writes. Per-source isolation and counters match the
    sequential path; only wall-clock time differs."""
    for key in scrapers:  # stable, pre-created SourceStats
        stats.source(key)

    work: queue.Queue = queue.Queue()

    def produce(key: str, scraper) -> None:
        try:
            for raw in itertools.islice(scraper.search(req), req.max_results):
                processed = _process_raw(
                    raw, settings=settings, scoring=scoring, filters=filters,
                    segments=segments, enrich=req.enrich_websites,
                )
                work.put((key, "lead", processed))
        except Exception as exc:  # noqa: BLE001 - report, don't abort other sources
            work.put((key, "error", str(exc)))
        finally:
            work.put((key, "done", None))

    pool = ThreadPoolExecutor(max_workers=max_workers)
    try:
        for key, scraper in scrapers.items():
            pool.submit(produce, key, scraper)

        remaining = len(scrapers)
        while remaining > 0:
            key, kind, payload = work.get()
            ss = stats.source(key)
            if kind == "done":
                remaining -= 1
                session.commit()  # persist this source's batch on completion
            elif kind == "error":
                log.error("source '%s' failed: %s", key, payload)
                stats.errors[key] = payload
                ss.error = payload
            else:  # "lead"
                stats.found += 1
                ss.found += 1
                _apply_processed(session, payload, run_id, stats, ss)
    finally:
        pool.shutdown(wait=True)
    session.commit()


def run_search(
    req: SearchRequest,
    source_keys: list[str],
    *,
    settings: Optional[Settings] = None,
    max_workers: Optional[int] = None,
) -> RunStats:
    settings = settings or get_settings()
    scoring = get_scoring()
    filters = get_filters()
    segments = get_segments()
    if max_workers is None:
        max_workers = getattr(settings, "max_workers", 1) or 1

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

        if max_workers and max_workers > 1:
            _run_concurrent(req, scrapers, session, run.id, stats, settings, scoring, filters, segments, max_workers)
        else:
            _run_sequential(req, scrapers, session, run.id, stats, settings, scoring, filters, segments)

        run.found = stats.found
        run.kept = stats.kept
        run.dropped = stats.dropped
        run.created = stats.created
        run.updated = stats.updated
        run.source_stats = {key: s.as_dict() for key, s in stats.per_source.items()}
        run.status = "done_with_errors" if stats.errors else "done"
        run.error = "; ".join(f"{k}: {v}" for k, v in stats.errors.items()) or None
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()

    return stats
