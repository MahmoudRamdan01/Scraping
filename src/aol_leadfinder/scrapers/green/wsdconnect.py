"""World Shipping Directory (wsdconnect.com) — GREEN source, not yet implemented.

International freight forwarders / customs agents. Implement using the EgyDir
pattern, then set ``enabled: true`` for ``wsdconnect`` in config/sources.yaml.
"""
from __future__ import annotations

from typing import Iterator

from ..base import BaseScraper, RawLead, SearchRequest


class WsdConnectScraper(BaseScraper):
    key = "wsdconnect"
    label = "World Shipping Directory (wsdconnect.com)"
    tier = "green"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        raise NotImplementedError(
            "wsdconnect scraper not implemented yet — follow the EgyDir pattern."
        )
