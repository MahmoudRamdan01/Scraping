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
#
# "Freight Forwarder" is intentionally NARROW: only forwarder-/customs-specific
# terms, NOT bare "shipping/شحن" or "logistics" — those appear on every factory or
# shop that *ships its products* and were the root cause of product companies being
# mislabelled as forwarders (i.e. as our competitors). Generic shipping words live
# in INTENT_SIGNALS instead, where they correctly signal a *customer* who ships.
COMPANY_TYPE_SIGNALS: dict[str, list[str]] = {
    "Freight Forwarder": [
        "freight forwarder", "freight forwarding", "forwarder", "forwarding agent",
        "customs clearance", "customs broker", "customs brokerage", "nvocc",
        "bill of lading", "تخليص جمركي", "تخليص", "شحن دولي", "وكيل شحن", "ملاحة",
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

# Customer types — the businesses Air Ocean SELLS to (they need shipping).
_CUSTOMER_TYPES = ("Manufacturer", "Exporter", "Importer", "Distributor", "Ecommerce")
# Unambiguous "we ARE a forwarder/logistics provider" terms. Only these keep the
# Freight-Forwarder label when a customer signal is also present (a forwarder is a
# competitor, not a lead, so we never want to mislabel a real customer as one).
_STRONG_FORWARDER = (
    "freight forwarder", "freight forwarding", "forwarding agent", "customs clearance",
    "customs broker", "customs brokerage", "nvocc", "bill of lading", "تخليص جمركي",
    "شحن دولي", "وكيل شحن",
)

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

# E-commerce platform fingerprints (name -> markers). First match wins. Knowing the
# platform tells the sales team the shipping/fulfilment profile (D2C, frequent
# parcels) at a glance.
_STORE_PLATFORMS: list[tuple[str, tuple[str, ...]]] = [
    ("Shopify", ("myshopify.com", "cdn.shopify", "shopify.shop", "powered by shopify")),
    ("WooCommerce", ("woocommerce", "wp-content/plugins/woocommerce", "wc-ajax")),
    ("Salla", ("salla.sa", "salla.shop", "cdn.salla", "متجر سلة")),
    ("Zid", ("zid.store", "zid.sa", "متجر زد")),
    ("Magento", ("magento", "/static/version", "mage/cookies")),
    ("WordPress", ("wp-content", "wp-json")),
]


def detect_store_platform(text: Optional[str]) -> Optional[str]:
    """Identify the e-commerce platform from page text/markup, or None."""
    t = (text or "").lower()
    for name, markers in _STORE_PLATFORMS:
        if any(m in t for m in markers):
            return name
    return None


@dataclass
class CompanyIntel:
    company_type: str = "Unknown"
    shipping_intent: int = 0
    signals: list[str] = field(default_factory=list)
    has_online_store: bool = False
    is_competitor: bool = False  # True only for genuine freight-forwarder identity


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
        # Precedence: a customer signal beats a generic forwarder signal unless the
        # page carries explicit forwarder identity. Stops "we ship our products"
        # pages from being filed as competitors.
        if company_type == "Freight Forwarder" and not any(kw in t for kw in _STRONG_FORWARDER):
            customer_hits = {k: v for k, v in type_scores.items() if k in _CUSTOMER_TYPES}
            if customer_hits:
                company_type = max(customer_hits, key=customer_hits.get)
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
        is_competitor=(company_type == "Freight Forwarder"),
    )


def analyze_website_html(html: str, category: Optional[str] = None) -> CompanyIntel:
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    return classify_company(text, category)
