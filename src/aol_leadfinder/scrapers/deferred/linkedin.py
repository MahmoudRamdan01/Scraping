"""LinkedIn (DEFERRED — ToS/PDPL risk). Not implemented; see deferred/__init__.py."""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class LinkedInScraper(BaseScraper):
    key = "linkedin"
    label = "LinkedIn (DEFERRED — ToS risk)"
    tier = "deferred"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "LinkedIn scraping is a DEFERRED RED-zone source: it breaches LinkedIn's User "
            "Agreement (actively enforced; see hiQ v. LinkedIn). Intentionally not implemented. "
            "Compliant alternative: manual outreach via LinkedIn's own messaging."
        )
