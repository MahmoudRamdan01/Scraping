from aol_leadfinder.scrapers.green.freightclub import FreightClubScraper, _map_category


def test_parse_listing(fixtures_dir):
    html = (fixtures_dir / "freightclub_sample.html").read_text(encoding="utf-8")
    leads = FreightClubScraper.parse_listing(html, country="Egypt", category="Freight Forwarder")

    assert len(leads) == 3

    first = leads[0]
    assert first.company_name == "Foreign Logistics Int'l"
    assert first.source == "freightclub"
    assert first.phone_raw == "+201018861666"  # from tel: href
    assert first.country == "Egypt"
    assert first.source_url.endswith("/companies/foreign-logistics-intl/")
    assert first.category == "Freight Forwarder"

    # All three carry phone numbers (the whole point of this source)
    assert all(lead.phone_raw for lead in leads)


def test_category_mapping():
    assert _map_category("Freight Forwarder") == "Freight Forwarder"
    assert _map_category("logistics") == "Freight Forwarder"
    assert _map_category("Customs Clearance") == "Customs Clearance Offices"
    assert _map_category("Trucking") == "Trucking Companies"
    # Non-freight categories are not served by this directory
    assert _map_category("Cosmetics") is None
    assert _map_category("Pharmaceuticals") is None


def test_parse_empty_is_safe():
    assert FreightClubScraper.parse_listing("<html><body></body></html>") == []
