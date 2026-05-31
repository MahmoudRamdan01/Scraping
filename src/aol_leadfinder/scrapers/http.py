"""Shared HTTP fetch + generic contact extraction used by scrapers and enrichment.

Generic extractors (phone/email) let us pull contact data from company detail
pages and websites without knowing each site's exact markup. Anything they
return is later validated by the pipeline (phonenumbers), so loose matches are
fine — invalid ones get dropped downstream.
"""
from __future__ import annotations

import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.8",
}

_PHONE_RE = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def fetch_html(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def extract_phone_from_html(html: str) -> Optional[str]:
    """Prefer a tel: link; fall back to the first phone-like string in the text."""
    soup = BeautifulSoup(html, "lxml")
    tel = soup.select_one("a[href^='tel:']")
    if tel is not None and tel.get("href"):
        return tel["href"][4:].strip()
    match = _PHONE_RE.search(soup.get_text(" ", strip=True))
    return match.group(1).strip() if match else None


def extract_emails_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    for a in soup.select("a[href^='mailto:']"):
        email = a["href"][7:].split("?")[0].strip().lower()
        if email and email not in out:
            out.append(email)
    for match in _EMAIL_RE.findall(soup.get_text(" ", strip=True)):
        email = match.lower()
        if email not in out:
            out.append(email)
    return out
