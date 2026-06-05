from aol_leadfinder.scrapers.base import SearchRequest
from aol_leadfinder.scrapers.green.textile_council import TextileCouncilScraper


def test_parse_listing(fixtures_dir):
    html = (fixtures_dir / "textile_council_members.html").read_text(encoding="utf-8")
    leads = TextileCouncilScraper.parse_listing(html)

    assert len(leads) == 3
    first = leads[0]
    assert first.company_name == "Aksa Egypt Acrylic Fiber Industry (s.a.e)"
    assert first.source == "textile_council"
    assert first.category == "Textiles"
    assert first.country == "Egypt"
    assert first.source_url == (
        "https://textile-egypt.org/textile-egypt.org/members/"
        "aksa_egypt_acrylic_fiber_industry_(s.a.html"
    )
    # the listing carries no contacts — they're harvested from the detail page
    assert first.phone_raw is None
    assert {lead.company_name for lead in leads} >= {"Al Baraka Group For Spinning & Weaving"}


def test_parse_detail(fixtures_dir):
    html = (fixtures_dir / "textile_council_detail.html").read_text(encoding="utf-8")
    detail = TextileCouncilScraper.parse_detail(html)

    # validated E.164 phones, mobile first
    assert detail["phones"][0] == "+201001718493"
    assert "+20482600126" in detail["phones"]
    # company emails kept; the council's own textile-egypt.org address filtered out
    assert "khmoussa@almatex.com" in detail["emails"]
    assert detail["emails"] and all("textile-egypt.org" not in e for e in detail["emails"])
    assert detail["website"] == "http://www.almatex.com"


def test_search_gates_non_textile_category(monkeypatch):
    # All-textile directory: an unrelated category yields nothing and must not
    # even hit the network.
    s = TextileCouncilScraper({"rate_limit": {"min": 0.0, "max": 0.0}})

    def _boom(*args, **kwargs):
        raise AssertionError("should not fetch for a non-textile category")

    monkeypatch.setattr("aol_leadfinder.scrapers.green.textile_council.fetch_html", _boom)
    assert list(s.search(SearchRequest(category="Cosmetics", max_results=5))) == []
