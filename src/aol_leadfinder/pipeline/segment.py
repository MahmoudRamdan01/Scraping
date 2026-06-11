"""Targeting segments — which priority bucket a lead falls into.

Driven entirely by ``config/segments.yaml`` so the sales team can retune targeting
without code. Segments are coarse labels for reporting + the service floor; the
*score* (pipeline/score.py) is what actually ranks leads.

    P1         physical-product makers/traders (factories, manufacturers,
               importers/distributors of goods) — the highest-value targets.
    P2         e-commerce stores (they ship constantly: freight/customs/fulfilment).
    P3         exporters / export-council members / GOEIC.
    service    businesses that don't ship physical goods (marketing, accounting,
               software, clinics, law, HR, training, …) — floored, not targeted.
    competitor freight forwarders / logistics providers — never a lead.
    other      everything else.
"""
from __future__ import annotations

from typing import Any

_CUSTOMER_PRODUCT_TYPES = ("Manufacturer", "Importer", "Distributor")


def _text_of(norm: Any) -> str:
    parts = [
        getattr(norm, "category", None),
        getattr(norm, "company_name", None),
        getattr(norm, "description", None),
        getattr(norm, "product_type", None),
    ]
    return " ".join(p for p in parts if p).lower()


def classify_segment(norm: Any, cfg: dict | None = None) -> str:
    cfg = cfg or {}
    ctype = getattr(norm, "company_type", None) or ""

    # 1) Competitor — overrides everything (a forwarder is never our customer).
    if getattr(norm, "is_competitor", False) or ctype == "Freight Forwarder":
        return "competitor"

    cat = (getattr(norm, "category", None) or "").strip()
    p1 = set(cfg.get("p1_categories", []))
    p2 = set(cfg.get("p2_categories", []))
    p3 = set(cfg.get("p3_categories", []))
    p3_sources = set(cfg.get("p3_sources", []))
    service_kw = cfg.get("service_keywords", [])

    is_product = ctype in _CUSTOMER_PRODUCT_TYPES or cat in p1
    is_ecom = (
        bool(getattr(norm, "has_online_store", False))
        or bool(getattr(norm, "store_platform", None))
        or ctype == "Ecommerce"
        or cat in p2
    )
    is_export = ctype == "Exporter" or getattr(norm, "source", None) in p3_sources or cat in p3

    # 2) Service exclusion — but a clear product/ecom/export company is never service.
    if not (is_product or is_ecom or is_export):
        text = _text_of(norm)
        if any(kw.lower() in text for kw in service_kw):
            return "service"

    # 3) Priority buckets. P1 (makes/trades goods) outranks P2 so a factory that
    #    also sells online stays a P1 (its online store is a scoring bonus).
    if is_product:
        return "P1"
    if is_ecom:
        return "P2"
    if is_export:
        return "P3"
    return "other"
