from aol_leadfinder.scrapers.base import RawLead, SearchRequest
from aol_leadfinder.scrapers.yellow.yellowpages_eg import YellowPagesEgScraper


def test_parse_listing(fixtures_dir):
    html = (fixtures_dir / "yellowpages_eg_listing.html").read_text(encoding="utf-8")
    leads = YellowPagesEgScraper.parse_listing(html, category="Logistics")

    assert len(leads) == 3
    first = leads[0]
    assert first.company_name == "Memco For Land Transportation Services"
    assert first.source == "yellowpages_eg"
    assert first.country == "Egypt"
    assert first.city == "6th of october"
    assert first.governorate == "Giza"
    assert first.category == "Transport and Logistics Services"
    # protocol-relative href -> absolute https, query stripped
    assert first.source_url == (
        "https://yellowpages.com.eg/en/profile/"
        "memco-for-land-transportation-services/712627"
    )
    # company id is carried so search() can fetch phones from /getPhones/<id>
    assert first.raw["yp_id"] == "712627"
    # listing carries no phone — it's resolved per-company in search()
    assert first.phone_raw is None


def test_parse_listing_falls_back_to_request_category():
    # A row whose own category node is absent should inherit the request category.
    html = """<div class="item-row">
      <a class="item-title" href="//yellowpages.com.eg/en/profile/acme/55">Acme</a>
      <a class="address-text"><span>10 Test St, Maadi, Cairo.</span></a>
    </div>"""
    leads = YellowPagesEgScraper.parse_listing(html, category="Freight")
    assert len(leads) == 1
    assert leads[0].category == "Freight"
    assert leads[0].city == "Maadi"
    assert leads[0].governorate == "Cairo"
    assert leads[0].raw["yp_id"] == "55"


def test_parse_phones_real_response():
    # Verbatim body returned by GET /en/getPhones/712627/false
    payload = '[["0103-0090-009","0127-1411-117","0127-1411-119"],[],[]]'
    assert YellowPagesEgScraper.parse_phones(payload) == [
        "0103-0090-009",
        "0127-1411-117",
        "0127-1411-119",
    ]


def test_parse_phones_dedupes_and_survives_garbage():
    assert YellowPagesEgScraper.parse_phones('[["02-1234-567"],["02-1234-567"],[]]') == [
        "02-1234-567"
    ]
    assert YellowPagesEgScraper.parse_phones("not json") == []
    assert YellowPagesEgScraper.parse_phones("[]") == []


def test_query_prefers_curated_then_category_name():
    q = YellowPagesEgScraper._query
    # mapped category -> validated end-customer term
    assert q(SearchRequest(category="Pharmaceuticals")) == "pharmaceutical industries"
    # unmapped category -> English name; role is NOT appended (YP over-narrows)
    assert q(SearchRequest(category="Cosmetics", role="Manufacturer")) == "Cosmetics"
    # no category -> first keyword, else role, else empty
    assert q(SearchRequest(keywords=["furniture"], role="Factory")) == "furniture"
    assert q(SearchRequest(role="Importer")) == "Importer"
    assert q(SearchRequest()) == ""


def test_location_filter_matches_city_or_governorate():
    giza = RawLead(company_name="A", source="yellowpages_eg", city="6th of october", governorate="Giza")
    cairo = RawLead(company_name="B", source="yellowpages_eg", city="Nasr city", governorate="Cairo")
    # 'Giza' entered as the location keeps a Giza-governorate lead whose city is a
    # district — the old city-only filter dropped it.
    wanted = YellowPagesEgScraper._wanted_location(SearchRequest(city="Giza"))
    assert YellowPagesEgScraper._location_ok(giza, wanted) is True
    assert YellowPagesEgScraper._location_ok(cairo, wanted) is False
    # no location constraint -> everything passes
    assert YellowPagesEgScraper._location_ok(cairo, []) is True


def test_search_url_pagination_and_encoding():
    s = YellowPagesEgScraper({"base_url": "https://www.yellowpages.com.eg"})
    assert s._search_url("cosmetics", 1) == "https://www.yellowpages.com.eg/en/search/cosmetics"
    assert s._search_url("cosmetics", 2) == "https://www.yellowpages.com.eg/en/search/cosmetics/p2"
    assert s._search_url("plastic industries", 3).endswith("/en/search/plastic%20industries/p3")
