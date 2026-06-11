from aol_leadfinder.enrichment.intelligence import analyze_website_html, classify_company


def test_exporter_high_intent():
    intel = classify_company("We export cosmetics to GCC countries and the Middle East")
    assert intel.company_type == "Exporter"
    assert intel.shipping_intent >= 60
    assert any(s in intel.signals for s in ("export", "we export", "gcc"))


def test_manufacturer():
    intel = classify_company("Our factory has a modern production line for skincare manufacturing")
    assert intel.company_type == "Manufacturer"
    assert intel.shipping_intent > 0


def test_ecommerce_detected():
    intel = classify_company("Shop now! Add to cart. Powered by Shopify checkout.")
    assert intel.company_type == "Ecommerce"
    assert intel.has_online_store is True


def test_freight_from_category_fallback():
    intel = classify_company("welcome to our website", category="Freight Forwarder")
    assert intel.company_type == "Freight Forwarder"


def test_unknown_when_empty():
    intel = classify_company("")
    assert intel.company_type == "Unknown"
    assert intel.shipping_intent == 0


def test_analyze_website_html():
    html = "<html><body><h1>We import and wholesale electronics worldwide</h1></body></html>"
    intel = analyze_website_html(html)
    assert intel.company_type in {"Importer", "Distributor"}
    assert intel.shipping_intent > 0


def test_factory_that_ships_is_not_a_forwarder():
    # The old classifier filed this as "Freight Forwarder" because of "شحن"/"shipping";
    # a product company that merely ships is a CUSTOMER, not a competitor.
    intel = classify_company(
        "مصنع تصنيع عطور ومستحضرات تجميل — نوفر شحن لكل المحافظات. fast shipping available"
    )
    assert intel.company_type == "Manufacturer"
    assert intel.is_competitor is False


def test_real_forwarder_is_competitor():
    intel = classify_company(
        "We are a freight forwarder offering customs clearance and bill of lading services"
    )
    assert intel.company_type == "Freight Forwarder"
    assert intel.is_competitor is True


def test_category_forwarder_fallback_is_competitor():
    intel = classify_company("welcome to our website", category="Freight Forwarder")
    assert intel.company_type == "Freight Forwarder"
    assert intel.is_competitor is True


def test_customer_type_is_not_competitor():
    assert classify_company("We export garments to Europe").is_competitor is False
