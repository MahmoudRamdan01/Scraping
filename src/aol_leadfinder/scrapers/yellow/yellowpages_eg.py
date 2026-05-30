"""Yellow Pages Egypt (yellowpages.com.eg) — YELLOW source (Phase 2).

Cloudflare-protected; needs Playwright + stealth and degrades to low volume
(~100-300/day single IP). Best-effort, fails gracefully. Not implemented yet.
"""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class YellowPagesEgScraper(BaseScraper):
    key = "yellowpages_eg"
    label = "Yellow Pages Egypt (yellowpages.com.eg)"
    tier = "yellow"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "yellowpages_eg scraper is a Phase 2 task (Cloudflare + Playwright). Not implemented yet."
        )
