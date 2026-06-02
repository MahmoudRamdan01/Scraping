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
