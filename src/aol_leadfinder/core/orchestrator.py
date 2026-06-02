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
from ..enrichment.crawler import crawl_website
from ..enrichment.intelligence import classify_company
from ..logging_setup import get_logger
from ..pipeline.filters import passes_filters
from ..pipeline.normalize import normalize_lead
from ..pipeline.score import score_lead
from ..pipeline.validate import validate_lead
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
    quarantined: int = 0
    created: int = 0
    updated: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    quarantine_reasons: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    run_id: Optional[int] = None

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
    if intel.markets:
        norm.target_markets = intel.markets
    if not norm.email and intel.emails:
        norm.email = intel.emails[0]

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
                    # Company Intelligence from the listing description (offline, free).
                    # Falls back to the category when there's no description text.
                    if norm.description or norm.category:
                        intel = classify_company(norm.description or "", norm.category)
                        norm.company_type = intel.company_type
                        norm.shipping_intent = intel.shipping_intent
                        if intel.has_online_store:
                            norm.has_online_store = True
                    # Optional deep website crawl (fills phone/email/type/intent)
                    if req.enrich_websites and norm.website:
                        _enrich_website(norm, settings.default_region)
                    # Structural validation BEFORE quality filters: broken data
                    # (no identity / no contact / bad phone) is quarantined — kept
                    # for review, excluded from the working list — never silently
                    # dropped and never allowed to pollute real leads.
                    valid, vreason = validate_lead(norm)
                    if not valid:
                        upsert_lead(session, norm, run.id, quarantine_reason=vreason)
                        stats.quarantine(vreason)
                        continue
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
