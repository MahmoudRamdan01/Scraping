"""Instagram (DEFERRED — ToS/PDPL risk). Not implemented; see deferred/__init__.py."""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class InstagramScraper(BaseScraper):
    key = "instagram"
    label = "Instagram (DEFERRED — ToS risk)"
    tier = "deferred"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "Instagram scraping is a DEFERRED RED-zone source: it violates Instagram's ToS "
            "and may conflict with Egypt's PDPL. It is intentionally not implemented."
        )
