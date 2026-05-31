from aol_leadfinder.enrichment.intelligence import classify_company
from aol_leadfinder.scrapers.green.forwarding_companies import ForwardingCompaniesScraper


def test_parse_listing(fixtures_dir):
    html = (fixtures_dir / "forwardingcompanies_sample.html").read_text(encoding="utf-8")
    leads = ForwardingCompaniesScraper.parse_listing(html, category="Freight Forwarder")

    assert len(leads) == 2
    first = leads[0]
    assert first.company_name == "BAROUN MISR FOR CARGO"
    assert first.source == "forwarding_companies"
    assert first.source_url.endswith("/company/baroun-misr-for-cargo")
    assert first.city == "Cairo"
    assert first.country == "Egypt"
    assert "freight forwarding" in (first.description or "").lower()


def test_description_feeds_intelligence(fixtures_dir):
    html = (fixtures_dir / "forwardingcompanies_sample.html").read_text(encoding="utf-8")
    leads = ForwardingCompaniesScraper.parse_listing(html)
    # The second company says "import and export" -> Intelligence classifies it offline
    intel = classify_company(leads[1].description, "Freight Forwarder")
    assert intel.shipping_intent > 0


def test_parse_empty_is_safe():
    assert ForwardingCompaniesScraper.parse_listing("<html><body></body></html>") == []
