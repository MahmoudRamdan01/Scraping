"""Offline demo scraper. Proves the end-to-end pipeline without any network.

It returns a small, varied set of fake leads so you can see filtering and
scoring in action (some are dropped as inactive / no-phone / no-website).
"""
from __future__ import annotations

from datetime import date
from typing import Iterator

from .base import BaseScraper, RawLead, SearchRequest


class DummyScraper(BaseScraper):
    key = "dummy"
    label = "Demo data (offline)"
    tier = "green"

    def search(self, req: SearchRequest) -> Iterator[RawLead]:
        city = req.city or "Alexandria"
        category = req.category or "Cosmetics"
        today_year = date.today().year

        samples = [
            RawLead(
                company_name="Nile Beauty Cosmetics",
                source=self.key,
                source_url="https://example.com/nile-beauty",
                phone_raw="+20 100 123 4567",
                email="info@nilebeauty.example",
                website="https://nilebeauty.example",
                address="Smouha, Alexandria",
                city=city,
                governorate="Alexandria",
                category=category,
                social_links={"linkedin": "https://linkedin.com/company/nile-beauty"},
                followers=5400,
                last_activity_date=date(today_year, max(1, date.today().month - 1), 10),
                rating=4.6,
                branches=3,
                has_online_store=True,
            ),
            RawLead(
                company_name="Pharaoh Pharma Supplies",
                source=self.key,
                phone_raw="01200000000",
                website="pharaohpharma.example",
                city=city,
                category="Pharmaceuticals",
                followers=1300,
                last_activity_date=date(today_year, 1, 5),
                rating=4.1,
            ),
            # Dropped: last active years ago (inactive page)
            RawLead(
                company_name="Old Gift Corner",
                source=self.key,
                phone_raw="+20 122 555 7788",
                website="https://oldgift.example",
                city=city,
                category="Gift Shops",
                followers=800,
                last_activity_date=date(2021, 6, 1),
            ),
            # Dropped: no phone number
            RawLead(
                company_name="No Phone Trading",
                source=self.key,
                website="https://nophone.example",
                city=city,
                category=category,
                followers=2000,
                last_activity_date=date(today_year, 2, 1),
            ),
            # Dropped (when require_website): individual seller, no site
            RawLead(
                company_name="Street Seller",
                source=self.key,
                phone_raw="+20 111 222 3333",
                city=city,
                category=category,
                followers=40,
                last_activity_date=date(today_year, 3, 1),
            ),
        ]
        for lead in samples:
            yield lead
