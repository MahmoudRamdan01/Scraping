"""Google Maps query building + label cleaning (pure, offline)."""
from aol_leadfinder.scrapers.base import SearchRequest
from aol_leadfinder.scrapers.yellow.google_maps import _clean_label, build_query


def test_build_query_end_customer():
    q = build_query(SearchRequest(country="Egypt", city="Cairo", category="Cosmetics", role="Manufacturer"))
    assert q == "Cosmetics manufacturers in Cairo Egypt"


def test_build_query_food_importers_alexandria():
    q = build_query(SearchRequest(country="Egypt", city="Alexandria", category="Food Suppliers", role="Importer"))
    assert q == "Food Suppliers importers in Alexandria Egypt"


def test_build_query_pharma_factories_borg():
    q = build_query(SearchRequest(country="Egypt", city="Borg El Arab", category="Pharmaceuticals", role="Factory"))
    assert q == "Pharmaceuticals factories in Borg El Arab Egypt"


def test_build_query_without_role():
    q = build_query(SearchRequest(country="Egypt", city="Cairo", category="Garments & Textiles"))
    assert q == "Garments & Textiles in Cairo Egypt"


def test_build_query_custom_role_falls_back_to_lowercase():
    q = build_query(SearchRequest(country="Egypt", city="Giza", category="Furniture", role="Trader"))
    assert q == "Furniture trader in Giza Egypt"


def test_clean_label_strips_prefixes():
    assert _clean_label("Phone: +20 2 22749776") == "+20 2 22749776"
    assert _clean_label("Website: ecc-hub.com") == "ecc-hub.com"
    assert _clean_label("Address: 62 Makram Ebeid, Nasr City") == "62 Makram Ebeid, Nasr City"
    assert _clean_label(None) is None
