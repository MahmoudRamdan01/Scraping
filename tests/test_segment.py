"""Targeting segments — P1/P2/P3/service/competitor classification (config-driven)."""
from aol_leadfinder.config import get_segments
from aol_leadfinder.pipeline.normalize import NormalizedLead
from aol_leadfinder.pipeline.segment import classify_segment

CFG = get_segments()


def _lead(**kw):
    return NormalizedLead(company_name=kw.pop("name", "X"), company_name_norm="x", source=kw.pop("source", "s"), **kw)


def test_manufacturer_of_products_is_p1():
    assert classify_segment(_lead(company_type="Manufacturer", category="Cosmetics"), CFG) == "P1"


def test_ecommerce_is_p2():
    assert classify_segment(_lead(company_type="Ecommerce"), CFG) == "P2"
    assert classify_segment(_lead(has_online_store=True, category="Gift Shops"), CFG) == "P2"


def test_factory_with_store_stays_p1_not_p2():
    # A maker that also sells online is a P1 (the online store is a scoring bonus).
    assert classify_segment(_lead(company_type="Manufacturer", has_online_store=True), CFG) == "P1"


def test_export_council_source_is_p3():
    assert classify_segment(_lead(source="aece", company_type="Exporter"), CFG) == "P3"
    assert classify_segment(_lead(category="Import & Export"), CFG) == "P3"


def test_competitor_overrides_everything():
    assert classify_segment(_lead(company_type="Freight Forwarder"), CFG) == "competitor"
    assert classify_segment(_lead(is_competitor=True, category="Cosmetics"), CFG) == "competitor"


def test_service_company_is_floored_segment():
    assert classify_segment(_lead(name="Bright Marketing Agency", category="Marketing"), CFG) == "service"
    assert classify_segment(_lead(name="شركة استشارات إدارية"), CFG) == "service"


def test_service_keyword_does_not_steal_a_product_company():
    # "consulting" in a description must not reclassify a real manufacturer.
    lead = _lead(company_type="Manufacturer", category="Textiles", description="we also offer consulting")
    assert classify_segment(lead, CFG) == "P1"


def test_unknown_is_other():
    assert classify_segment(_lead(), CFG) == "other"
