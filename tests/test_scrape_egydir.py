from aol_leadfinder.scrapers.green.egydir import EgyDirScraper


def test_parse_listing(fixtures_dir):
    html = (fixtures_dir / "egydir_sample.html").read_text(encoding="utf-8")
    leads = EgyDirScraper.parse_listing(html, default_city="Alexandria", category="Cosmetics")

    assert len(leads) == 3

    first = leads[0]
    assert first.company_name == "Nile Beauty Cosmetics"
    assert first.source == "egydir"
    assert first.phone_raw == "+201001234567"  # from tel: href
    assert first.website == "https://nilebeauty.example"
    assert first.category == "Cosmetics"
    assert first.source_url.endswith("/company/nile-beauty")
    assert first.city == "Alexandria"

    # Second card: phone is plain text (no tel:), and there's no website link
    second = leads[1]
    assert second.company_name == "Cairo Pharma Trading"
    assert second.phone_raw == "+20 122 555 7788"
    assert second.website is None


def test_parse_listing_empty_html_is_safe():
    assert EgyDirScraper.parse_listing("<html><body></body></html>") == []
