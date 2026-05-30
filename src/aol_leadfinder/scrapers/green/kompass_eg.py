"""Kompass Egypt (eg.kompass.com) — GREEN source, not yet implemented.

To implement: copy the EgyDir pattern — add a pure ``parse_listing(html)``
classmethod with the right CSS selectors, record a fixture in
tests/fixtures/kompass_sample.html, and add a parse test. Then set
``enabled: true`` for ``kompass_eg`` in config/sources.yaml.
"""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class KompassEgScraper(BaseScraper):
    key = "kompass_eg"
    label = "Kompass Egypt (eg.kompass.com)"
    tier = "green"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "kompass_eg scraper not implemented yet — follow the EgyDir pattern."
        )
