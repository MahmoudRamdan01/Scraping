from aol_leadfinder.scrapers.base import SearchRequest
from aol_leadfinder.scrapers.green.aece import AECEScraper
from aol_leadfinder.scrapers.http import decode_cf_emails


def test_parse_listing(fixtures_dir):
    html = (fixtures_dir / "aece_directory.html").read_text(encoding="utf-8")
    leads = AECEScraper.parse_listing(html)

    assert len(leads) == 3
    first = leads[0]
    assert first.company_name == "Abo Shaar Brothers “Royal Tex”"
    assert first.source == "aece"
    assert first.category == "Garments"
    assert first.country == "Egypt"
    assert first.source_url == "https://aecegy.com/business-directory/abo-shaar-brothers-royal-tex/"
    assert first.phone_raw is None  # contacts come from the member page
    assert {lead.company_name for lead in leads} >= {"Ace Apparel Egypt"}


def test_parse_detail_recovers_cf_emails(fixtures_dir):
    html = (fixtures_dir / "aece_detail.html").read_text(encoding="utf-8")
    detail = AECEScraper.parse_detail(html)

    assert detail["phones"][0] == "+20225937958"
    # emails are Cloudflare-obfuscated on the page; they must be decoded, and the
    # council's own aecegy.com address filtered out.
    assert "info@royal-cotton.com" in detail["emails"]
    assert detail["emails"] and all("aecegy.com" not in e for e in detail["emails"])
    assert detail["address"] and "Cairo" in detail["address"]


def test_decode_cf_emails_unit():
    # data-cfemail hex: first byte is the XOR key for the rest.
    plain = "info@royal-cotton.com"
    key = 0x2a
    payload = bytes([key]) + bytes(ord(c) ^ key for c in plain)
    html = f'<a href="/cdn-cgi/l/email-protection" data-cfemail="{payload.hex()}">[email protected]</a>'
    assert decode_cf_emails(html) == [plain]
    assert decode_cf_emails("<p>no cf email here</p>") == []


def test_search_gates_non_apparel_category(monkeypatch):
    s = AECEScraper({"rate_limit": {"min": 0.0, "max": 0.0}})

    def _boom(*args, **kwargs):
        raise AssertionError("should not fetch for a non-apparel category")

    monkeypatch.setattr("aol_leadfinder.scrapers.green.aece.fetch_html", _boom)
    assert list(s.search(SearchRequest(category="Pharmaceuticals", max_results=5))) == []
