"""Forwarding Companies (forwardingcompanies.com) — GREEN source, not implemented.

Global freight directory (150+ countries). Implement using the EgyDir pattern,
then set ``enabled: true`` for ``forwarding_companies`` in config/sources.yaml.
"""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class ForwardingCompaniesScraper(BaseScraper):
    key = "forwarding_companies"
    label = "Forwarding Companies (forwardingcompanies.com)"
    tier = "green"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "forwarding_companies scraper not implemented yet — follow the EgyDir pattern."
        )
