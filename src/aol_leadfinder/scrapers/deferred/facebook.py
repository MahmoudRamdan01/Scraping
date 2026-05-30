"""Facebook (DEFERRED — ToS/PDPL risk). Not implemented; see deferred/__init__.py."""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class FacebookScraper(BaseScraper):
    key = "facebook"
    label = "Facebook (DEFERRED — ToS risk)"
    tier = "deferred"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "Facebook scraping is a DEFERRED RED-zone source: it violates Facebook's ToS "
            "and may conflict with Egypt's PDPL. It is intentionally not implemented. "
            "Compliant alternative: manual research + opt-in lead forms."
        )
