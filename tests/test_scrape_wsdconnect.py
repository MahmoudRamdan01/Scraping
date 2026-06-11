from aol_leadfinder.scrapers.green.wsdconnect import WsdConnectScraper
from aol_leadfinder.scrapers.http import extract_phone_from_html


def test_parse_listing(fixtures_dir):
    html = (fixtures_dir / "wsdconnect_listing.html").read_text(encoding="utf-8")
    leads = WsdConnectScraper.parse_listing(html, category="Freight Forwarder")

    assert len(leads) == 2
    first = leads[0]
    assert first.company_name == "Aquacity water logistics"
    assert first.source == "wsdconnect"
    assert first.email == "info@aquacitygroups.net"
    assert first.website == "https://www.aquacitygroups.net"
    # location is the first .listing-item only — service tags / "+N more" ports
    # in the later .listing-item rows must not leak into city/country.
    assert first.city == "Gandhidham"
    assert first.country == "India"
    assert first.source_url.endswith("/listings/aquacity-water-logistics/cha-services")
    assert first.category == "CHA Services"


def test_detail_phone_extraction(fixtures_dir):
    # extract_phone_from_html is the generic primitive used by website enrichment
    html = (fixtures_dir / "wsdconnect_detail.html").read_text(encoding="utf-8")
    assert extract_phone_from_html(html) == "+201234567890"
