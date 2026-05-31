"""Country / target-market detection from company website text.

Detects which markets a company talks about (GCC, Europe, Africa, …). More
non-local markets => higher shipping intent (they move goods across borders).
Pure and deterministic -> unit-testable.
"""
from __future__ import annotations

MARKET_SIGNALS: dict[str, list[str]] = {
    "GCC": [
        "gcc", "gulf", "الخليج", "saudi", "ksa", "uae", "emirates", "dubai", "jeddah",
        "riyadh", "qatar", "kuwait", "bahrain", "oman", "السعودية", "الإمارات", "قطر", "الكويت",
    ],
    "Europe": [
        "europe", "european", " eu ", "germany", "france", "italy", "spain",
        "united kingdom", " uk ", "netherlands", "أوروبا",
    ],
    "Africa": ["africa", "african", "sudan", "libya", "nigeria", "kenya", "morocco", "إفريقيا", "أفريقيا", "السودان"],
    "Americas": ["usa", "u.s.", "united states", " america", "canada", "brazil", "أمريكا"],
    "Asia": ["china", "india", " asia", "far east", "singapore", "الصين", "الهند", "آسيا"],
    "Local (Egypt)": ["egypt", "cairo", "alexandria", "مصر", "القاهرة", "الإسكندرية"],
}


def detect_markets(text: str | None) -> list[str]:
    if not text:
        return []
    haystack = " " + text.lower() + " "
    return [market for market, kws in MARKET_SIGNALS.items() if any(k in haystack for k in kws)]
