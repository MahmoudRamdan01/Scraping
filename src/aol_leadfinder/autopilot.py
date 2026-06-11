"""Autopilot — the unattended daily run.

Builds a rotating slice of high-priority search segments (physical-product makers,
e-commerce, export councils), scrapes + enriches + scores them through the normal
pipeline, then APPENDS only the new leads to the team's Google Sheet. Designed to
run headless on GitHub Actions once a day.

Run it locally with::

    python -m aol_leadfinder.autopilot --dry-run        # scrape+score, skip the sheet
    python -m aol_leadfinder.autopilot                  # full run + sheet append

The Sheet is the durable de-dup authority: ``append_new_leads`` reads the phone/
domain keys already there and skips them, so cross-run de-dup is correct even
though the CI database is ephemeral.
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .config import get_settings, load_yaml
from .core.orchestrator import run_search
from .logging_setup import get_logger
from .scrapers.base import SearchRequest
from .scrapers.yellow.google_maps import build_query
from .storage.db import get_engine, mark_pushed_to_sheet, read_all_leads

log = get_logger("autopilot")


def load_plan() -> dict:
    return load_yaml("autopilot.yaml")


def build_segments(
    cfg: dict, *, today_ordinal: int, max_results: int, enrich: bool, limit: Optional[int] = None
) -> list[SearchRequest]:
    """The directory segments to run today (rotating daily slice, de-duped queries).

    Pure: depends only on ``cfg`` + the day number, so it's fully unit-testable.
    """
    country = cfg.get("country", "Egypt")
    roles = cfg.get("roles", [])
    govs = cfg.get("governorates", [])

    combos: list[tuple[str, Optional[str], str]] = []
    for category in cfg.get("categories", []):
        for role in roles:
            for gov in govs:
                combos.append((category, role, gov))
    for category in cfg.get("ecommerce_categories", []):  # P2 — no role
        for gov in govs:
            combos.append((category, None, gov))

    # Rotating daily slice: a different window each day, cycling through everything.
    if limit and 0 < limit < len(combos):
        slices = math.ceil(len(combos) / limit)
        start = (today_ordinal % slices) * limit
        combos = combos[start:start + limit]

    segments: list[SearchRequest] = []
    seen_queries: set[str] = set()
    for category, role, gov in combos:
        req = SearchRequest(
            country=country, city=gov, category=category, role=role,
            max_results=max_results, enrich_websites=enrich,
        )
        # Collapse combos that produce an identical Maps query (defensive de-dup).
        q = build_query(req)
        if q in seen_queries:
            continue
        seen_queries.add(q)
        segments.append(req)
    return segments


@dataclass
class AutopilotResult:
    segments: int = 0
    found: int = 0
    kept: int = 0
    created: int = 0
    appended: int = 0
    skipped: int = 0
    errors: int = 0


def run_autopilot(
    *,
    dry_run: bool = False,
    enrich: Optional[bool] = None,
    max_workers: Optional[int] = None,
    max_results: Optional[int] = None,
    limit: Optional[int] = None,
    push: bool = True,
) -> AutopilotResult:
    cfg = load_plan()
    settings = get_settings()
    enrich = cfg.get("enrich", True) if enrich is None else enrich
    max_results = max_results or int(cfg.get("max_results_per_source", 30))
    limit = limit if limit is not None else int(cfg.get("daily_segment_limit", 12))
    directory_sources = cfg.get("directory_sources", ["yellowpages_eg"])
    council_sources = cfg.get("council_sources", [])

    result = AutopilotResult()

    def _accumulate(stats) -> None:
        result.found += stats.found
        result.kept += stats.kept
        result.created += stats.created
        result.errors += len(stats.errors)

    # 1) Export councils — swept once (they list all members regardless of segment).
    if council_sources:
        log.info("autopilot: councils %s", council_sources)
        council_req = SearchRequest(country=cfg.get("country", "Egypt"), max_results=max_results, enrich_websites=enrich)
        _accumulate(run_search(council_req, council_sources, max_workers=max_workers))

    # 2) Directory segments — today's rotating slice.
    segments = build_segments(
        cfg, today_ordinal=date.today().toordinal(), max_results=max_results, enrich=enrich, limit=limit
    )
    result.segments = len(segments)
    for i, req in enumerate(segments, start=1):
        log.info("autopilot: segment %d/%d — %s/%s in %s", i, len(segments), req.category, req.role, req.city)
        _accumulate(run_search(req, directory_sources, max_workers=max_workers))

    # 3) Append new leads to the team sheet (the durable de-dup authority).
    engine = get_engine(settings.db_path)
    leads = read_all_leads(engine)
    if push and not dry_run:
        from .storage.sheets_sync import SheetsNotConfigured, append_new_leads, is_configured

        if is_configured() and settings.sheet_id:
            try:
                appended = append_new_leads(leads)
                mark_pushed_to_sheet(engine, [lead.id for lead in appended.leads])
                result.appended = appended.appended
                result.skipped = appended.skipped
                log.info("autopilot: appended %d new leads (skipped %d)", appended.appended, appended.skipped)
            except SheetsNotConfigured as exc:
                log.warning("autopilot: sheet not configured: %s", exc)
        else:
            log.warning("autopilot: Google Sheet not configured — skipping append (set GOOGLE_SHEET_ID + creds)")

    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Air Ocean Lead Finder — daily autopilot run.")
    parser.add_argument("--dry-run", action="store_true", help="scrape + score but do NOT append to the sheet")
    parser.add_argument("--no-enrich", action="store_true", help="skip website enrichment (faster, lower quality)")
    parser.add_argument("--max-workers", type=int, default=None, help="search concurrency (default from env/Settings)")
    parser.add_argument("--max-results", type=int, default=None, help="override per-source result cap")
    parser.add_argument("--limit-segments", type=int, default=None, help="override how many directory segments to run")
    args = parser.parse_args(argv)

    result = run_autopilot(
        dry_run=args.dry_run,
        enrich=False if args.no_enrich else None,
        max_workers=args.max_workers,
        max_results=args.max_results,
        limit=args.limit_segments,
    )
    print(
        f"autopilot: segments={result.segments} found={result.found} kept={result.kept} "
        f"new={result.created} appended={result.appended} skipped={result.skipped} errors={result.errors}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
