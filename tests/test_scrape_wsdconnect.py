from aol_leadfinder.scrapers.green.wsdconnect import WsdConnectScraper
from aol_leadfinder.scrapers.http import extract_phone_from_html


def test_parse_listing(fixtures_dir):
    html = (fixtures_dir / "wsdconnect_listing.html").read_text(encoding="utf-8")
    leads = WsdConnectScraper.parse_listing(html, category="Freight Forwarder")

    assert len(leads) == 2
    first = leads[0]
    assert first.company_name == "Alex Cargo Services"
    assert first.source == "wsdconnect"
    assert first.email == "info@alexcargo.example"
    assert first.website == "https://alexcargo.example"
    assert first.city == "Alexandria"
    assert first.country == "Egypt"
    assert first.source_url.endswith("/listings/alex-cargo/freight-forwarding")
    assert first.category == "Freight Forwarding"


def test_detail_phone_extraction(fixtures_dir):
    # extract_phone_from_html is the generic primitive used by website enrichment
    html = (fixtures_dir / "wsdconnect_detail.html").read_text(encoding="utf-8")
    assert extract_phone_from_html(html) == "+201234567890"
