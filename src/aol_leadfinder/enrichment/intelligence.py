"""Company Intelligence Engine.

Given a company's website text (or any descriptive text), classify the company
type and compute a 0-100 **Shipping Intent Score** — how likely the company
needs shipping/freight services. This is what turns a raw lead into a
*qualified* lead for Air Ocean Line.

The core (`classify_company`) is pure and deterministic (keyword signals), so it
is fully unit-testable offline. `analyze_website_html` just extracts visible
text first. Crawling the website itself is done by the orchestrator (opt-in),
because it needs the network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

# Signals that indicate a company *type* (Arabic + English).
COMPANY_TYPE_SIGNALS: dict[str, list[str]] = {
    "Freight Forwarder": [
        "freight", "forwarder", "forwarding", "logistics", "customs clearance",
        "شحن", "تخليص", "لوجستيات", "شحن دولي",
    ],
    "Manufacturer": [
        "manufacturer", "manufacturing", "factory", "we produce", "our factory",
        "production line", "مصنع", "تصنيع", "إنتاج", "خط إنتاج",
    ],
    "Importer": ["importer", "we import", "import of", "استيراد", "مستورد"],
    "Exporter": ["exporter", "we export", "export to", "export of", "exporting", "تصدير", "مصدر", "مصدّر"],
    "Distributor": [
        "distributor", "distribution", "wholesale", "wholesaler",
        "موزع", "توزيع", "جملة", "تاجر جملة",
    ],
    "Ecommerce": [
        "add to cart", "shop now", "online store", "checkout", "shopify",
        "woocommerce", "salla", "zid", "متجر إلكتروني", "اطلب الآن", "أضف إلى السلة", "سلة", "زد",
    ],
}

# Phrases that signal shipping intent and their weights.
INTENT_SIGNALS: dict[str, int] = {
    "we export": 30, "we import": 30, "international shipping": 30, "worldwide shipping": 30,
    "شحن دولي": 30, "export": 25, "import": 25, "تصدير": 25, "استيراد": 25,
    "gcc": 20, "middle east": 15, "ship to": 15, "delivery": 10, "shipping": 10,
    "wholesale": 15, "distributor": 15, "جملة": 15, "الخليج": 20, "توصيل": 10, "شحن": 10,
}

# Base intent by company type (a manufacturer/exporter inherently needs freight).
_TYPE_BASE_INTENT = {
    "Exporter": 35, "Importer": 35, "Manufacturer": 25,
    "Distributor": 20, "Freight Forwarder": 25, "Ecommerce": 15, "Unknown": 0,
}

_ECOMMERCE_MARKERS = ["shopify.shop", "/cart", "woocommerce", "add to cart", "shop now", "salla", "zid"]


@dataclass
class CompanyIntel:
    company_type: str = "Unknown"
    shipping_intent: int = 0
    signals: list[str] = field(default_factory=list)
    has_online_store: bool = False


def classify_company(text: Optional[str], category: Optional[str] = None) -> CompanyIntel:
    t = (text or "").lower()

    type_scores: dict[str, int] = {}
    for ctype, keywords in COMPANY_TYPE_SIGNALS.items():
        hits = sum(1 for kw in keywords if kw in t)
        if hits:
            type_scores[ctype] = hits

    has_store = any(marker in t for marker in _ECOMMERCE_MARKERS)
    if has_store:
        type_scores["Ecommerce"] = type_scores.get("Ecommerce", 0) + 1

    if type_scores:
        company_type = max(type_scores, key=type_scores.get)
    elif category and ("freight" in category.lower() or "forwarder" in category.lower()):
        company_type = "Freight Forwarder"
    else:
        company_type = "Unknown"

    intent = 0
    matched: list[str] = []
    for phrase, points in INTENT_SIGNALS.items():
        if phrase in t:
            intent += points
            matched.append(phrase)
    if has_store:
        intent += 10
    intent = min(intent + _TYPE_BASE_INTENT.get(company_type, 0), 100)

    return CompanyIntel(
        company_type=company_type,
        shipping_intent=intent,
        signals=sorted(set(matched)),
        has_online_store=has_store,
    )


def analyze_website_html(html: str, category: Optional[str] = None) -> CompanyIntel:
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    return classify_company(text, category)
