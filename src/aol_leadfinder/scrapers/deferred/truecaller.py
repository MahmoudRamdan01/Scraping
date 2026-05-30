"""Truecaller enrichment (DEFERRED — ToS/PDPL risk). Not implemented."""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class TruecallerScraper(BaseScraper):
    key = "truecaller"
    label = "Truecaller enrichment (DEFERRED — ToS risk)"
    tier = "deferred"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "Truecaller lookups are a DEFERRED RED-zone source: they violate Truecaller's ToS "
            "and reveal individuals' personal data (PDPL risk). Intentionally not implemented."
        )
