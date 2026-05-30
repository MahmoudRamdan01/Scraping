"""Freight Club Directory (freightclub.net) — GREEN source, not yet implemented.

Egypt/Gulf freight forwarders. Implement using the EgyDir pattern, then set
``enabled: true`` for ``freightclub`` in config/sources.yaml.
"""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class FreightClubScraper(BaseScraper):
    key = "freightclub"
    label = "Freight Club Directory (freightclub.net)"
    tier = "green"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "freightclub scraper not implemented yet — follow the EgyDir pattern."
        )
