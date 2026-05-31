from aol_leadfinder.enrichment.crawler import crawl_website, discover_subpages
from aol_leadfinder.enrichment.markets import detect_markets

PAGES = {
    "https://acme.example/": (
        "<html><body>"
        "<a href='/about'>About Us</a> <a href='/contact'>Contact</a>"
        "<a href='https://facebook.com/acme'>fb</a>"
        "<p>We export cosmetics to GCC countries and Europe.</p>"
        "</body></html>"
    ),
    "https://acme.example/about": (
        "<html><body>Our factory manufactures skincare and we export worldwide. "
        "<a href='mailto:info@acme.example'>email</a></body></html>"
    ),
    "https://acme.example/contact": (
        "<html><body><a href='tel:+201234567890'>call</a> sales@acme.example</body></html>"
    ),
}


def _fake_fetch(url: str) -> str:
    return PAGES[url]


def test_detect_markets():
    markets = detect_markets("We export to Saudi Arabia, UAE and Europe from Egypt")
    assert "GCC" in markets
    assert "Europe" in markets
    assert "Local (Egypt)" in markets


def test_detect_markets_empty():
    assert detect_markets("") == []


def test_discover_subpages():
    subs = discover_subpages(PAGES["https://acme.example/"], "https://acme.example/", limit=3)
    assert any(s.endswith("/about") for s in subs)
    assert any(s.endswith("/contact") for s in subs)
    # off-domain (facebook) link must not be followed
    assert all("facebook.com" not in s for s in subs)


def test_crawl_website_offline():
    wi = crawl_website("https://acme.example/", category="Cosmetics", fetch=_fake_fetch, delay=0)
    assert wi.pages_crawled == 3
    assert wi.company_type in {"Exporter", "Manufacturer"}
    assert "info@acme.example" in wi.emails
    assert "+201234567890" in wi.phones
    assert "GCC" in wi.markets and "Europe" in wi.markets
    assert wi.shipping_intent >= 60  # export + multiple markets


def test_crawl_unreachable_is_safe():
    def boom(url):
        raise OSError("no network")

    wi = crawl_website("https://nope.example/", fetch=boom)
    assert wi.pages_crawled == 0
    assert wi.company_type == "Unknown"
