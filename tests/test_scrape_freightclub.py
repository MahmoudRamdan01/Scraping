from aol_leadfinder.scrapers.green.freightclub import FreightClubScraper, _map_category


def test_parse_listing_pairs_name_and_phone(fixtures_dir):
    html = (fixtures_dir / "freightclub_sample.html").read_text(encoding="utf-8")
    leads = FreightClubScraper.parse_listing(html, country="Egypt", category="Freight Forwarder")

    assert len(leads) == 2  # the /companies/feed/ link has no phone -> not emitted
    first = leads[0]
    assert first.company_name == "Foreign Group Intl (F.G.I)"
    assert first.source == "freightclub"
    assert first.phone_raw == "+201018861666"
    assert first.source_url.endswith("/companies/foreign-group-intl-f-g-i/")
    assert first.country == "Egypt"
    assert all(lead.phone_raw for lead in leads)


def test_category_mapping():
    assert _map_category("Freight Forwarder") == "Freight Forwarder"
    assert _map_category("logistics") == "Freight Forwarder"
    assert _map_category("Customs Clearance") == "Customs Clearance Offices"
    assert _map_category("Trucking") == "Trucking Companies"
    assert _map_category("Cosmetics") is None


def test_parse_empty_is_safe():
    assert FreightClubScraper.parse_listing("<html><body></body></html>") == []
