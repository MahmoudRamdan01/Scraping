"""Google Maps business listings — YELLOW source (Phase 2).

Highest-quality phone numbers but hard to scrape: needs Playwright + a real
(persistent, stealth) browser, conservative pacing, and checkpointing. Realistic
throughput is ~500-1000 listings/day on a single IP without proxies. Treat as
best-effort, never a hard dependency. Not implemented in this build.
"""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class GoogleMapsScraper(BaseScraper):
    key = "google_maps"
    label = "Google Maps (business listings)"
    tier = "yellow"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "google_maps scraper is a Phase 2 task (Playwright + stealth). Not implemented yet."
        )
