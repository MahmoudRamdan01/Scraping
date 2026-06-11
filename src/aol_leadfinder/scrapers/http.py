"""Shared HTTP fetch + generic contact extraction used by scrapers and enrichment.

Phone extraction is *quality-first*: it gathers candidates from WhatsApp links,
``tel:`` links, and visible text, then validates each with libphonenumber and
returns only valid E.164 numbers (WhatsApp/tel first). This avoids the classic
"first number on the page" bug where a fax, tax id, or price gets picked.
"""
from __future__ import annotations

import hashlib
import os
import random
import re
import time
from pathlib import Path
from typing import Optional

import phonenumbers
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.8",
}

_PHONE_RE = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Cloudflare email obfuscation: <a data-cfemail="HEX">, first byte = XOR key.
_CF_EMAIL_RE = re.compile(r'data-cfemail="([0-9a-fA-F]{6,})"')
# wa.me/<num>, api.whatsapp.com/send?phone=<num>, whatsapp://send?phone=<num>
_WHATSAPP_RE = re.compile(
    r"(?:wa\.me/|whatsapp\.com/send\?phone=|whatsapp://send\?phone=)\+?(\d{6,15})", re.I
)

# Emails that are never useful sales contacts.
_EMAIL_BAD_SUBSTR = (
    "example.com", "example.org", "sentry", "wixpress", "wix.com", "godaddy",
    "domain.com", "yourdomain", "email.com", "test@", "noreply", "no-reply",
)
_EMAIL_BAD_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")


def _insecure_default() -> bool:
    # Opt-in for environments with broken clocks / TLS-intercepting proxies.
    return str(os.environ.get("AOL_INSECURE_SSL", "false")).strip().lower() in {"1", "true", "yes", "on"}


# HTTP statuses worth a retry: rate-limit + transient server errors. A 4xx like
# 404/403 is terminal (the page won't appear by asking again), so it fails fast.
_RETRY_STATUS = {429, 500, 502, 503, 504}


# ---- Optional connection pooling + on-disk cache (both env-gated, OFF by default) ----
# When AOL_HTTP_POOL is unset the GET goes through a bare ``requests.get`` exactly as
# before, so the retry tests (which patch ``http.requests.get``) are unaffected. The
# pool + cache only activate for the autopilot / concurrent runs that set the env vars.
_SESSION: Optional[requests.Session] = None


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name, "false")).strip().lower() in {"1", "true", "yes", "on"}


def _session() -> requests.Session:
    """Lazily build a shared, thread-safe Session with a connection pool."""
    global _SESSION
    if _SESSION is None:
        sess = requests.Session()
        adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=0)
        sess.mount("http://", adapter)
        sess.mount("https://", adapter)
        _SESSION = sess
    return _SESSION


def _do_get(url: str, **kwargs):
    """One GET: pooled Session when AOL_HTTP_POOL is set, else a bare requests.get."""
    if _env_flag("AOL_HTTP_POOL"):
        return _session().get(url, **kwargs)
    return requests.get(url, **kwargs)


def _cache_dir() -> Optional[Path]:
    d = os.environ.get("AOL_HTTP_CACHE_DIR")
    return Path(d) if d else None


def _cache_ttl() -> float:
    try:
        return float(os.environ.get("AOL_HTTP_CACHE_TTL", "86400"))
    except (TypeError, ValueError):
        return 86400.0


def _cache_file(cache_dir: Path, url: str) -> Path:
    return cache_dir / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".html")


def _cache_read(url: str) -> Optional[str]:
    cdir = _cache_dir()
    if not cdir:
        return None
    path = _cache_file(cdir, url)
    try:
        if path.exists() and (time.time() - path.stat().st_mtime) < _cache_ttl():
            return path.read_text(encoding="utf-8")
    except OSError:
        return None
    return None


def _cache_write(url: str, text: str) -> None:
    cdir = _cache_dir()
    if not cdir:
        return
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        _cache_file(cdir, url).write_text(text, encoding="utf-8")
    except OSError:
        pass


def fetch_html(
    url: str,
    timeout: int = 20,
    verify: Optional[bool] = None,
    *,
    retries: int = 3,
    backoff_base: float = 1.5,
) -> str:
    """GET ``url`` and return its HTML, retrying only *transient* failures.

    Network errors, timeouts, and retryable HTTP statuses (429/5xx) are retried up
    to ``retries`` times with exponential backoff + jitter; non-retryable client
    errors (404/403/…) fail fast. Every scraper goes through this single function,
    so the resilience is inherited centrally instead of reimplemented per source.
    The success (200) path is a single request with zero added overhead.
    """
    if verify is None:
        verify = not _insecure_default()
    if not verify:
        import urllib3

        urllib3.disable_warnings()

    cached = _cache_read(url)
    if cached is not None:
        return cached

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = _do_get(url, headers=HEADERS, timeout=timeout, verify=verify)
        except requests.RequestException as exc:
            # Connection reset, DNS failure, timeout, etc.
            last_exc = exc
            if attempt >= retries:
                raise
            time.sleep(backoff_base ** attempt + random.uniform(0, 0.5))
            continue

        if resp.status_code in _RETRY_STATUS and attempt < retries:
            last_exc = requests.HTTPError(f"{resp.status_code} Server Error for url: {url}", response=resp)
            time.sleep(backoff_base ** attempt + random.uniform(0, 0.5))
            continue

        # 200 -> return; non-retryable 4xx or a final-attempt 5xx -> raise here
        # (outside the network except, so HTTPError is never re-caught as transient).
        resp.raise_for_status()
        _cache_write(url, resp.text)
        return resp.text

    raise last_exc if last_exc is not None else RuntimeError(f"fetch_html failed for {url}")


def best_e164(raw: str, region: str = "EG") -> Optional[str]:
    """Validate a raw phone string and return E.164, or None if not a valid number."""
    if not raw:
        return None
    try:
        num = phonenumbers.parse(str(raw).strip(), region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num):
        return None
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def extract_phones(html: str, region: str = "EG") -> list[str]:
    """All VALID E.164 phones on the page, WhatsApp & tel: links prioritized."""
    soup = BeautifulSoup(html, "lxml")
    candidates: list[tuple[int, str]] = []  # (priority, raw) — lower runs first

    for m in _WHATSAPP_RE.finditer(html):
        candidates.append((0, "+" + m.group(1)))
    for a in soup.select("a[href^='tel:']"):
        candidates.append((1, a.get("href", "")[4:]))
    text = soup.get_text(" ", strip=True)
    for m in _PHONE_RE.finditer(text):
        candidates.append((2, m.group(1)))

    out: list[str] = []
    for _, raw in sorted(candidates, key=lambda x: x[0]):
        e164 = best_e164(raw, region)
        if e164 and e164 not in out:
            out.append(e164)
    return out


def extract_phone_from_html(html: str, region: str = "EG") -> Optional[str]:
    """The single best (valid) phone on the page, or None."""
    phones = extract_phones(html, region)
    return phones[0] if phones else None


def extract_whatsapp_numbers(html: str, region: str = "EG") -> list[str]:
    """Valid E.164 numbers that are explicitly reachable on WhatsApp."""
    out: list[str] = []
    for m in _WHATSAPP_RE.finditer(html):
        e164 = best_e164("+" + m.group(1), region)
        if e164 and e164 not in out:
            out.append(e164)
    return out


def _is_useful_email(email: str) -> bool:
    low = email.lower()
    if any(bad in low for bad in _EMAIL_BAD_SUBSTR):
        return False
    if low.endswith(_EMAIL_BAD_EXT):
        return False
    return True


def extract_emails_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []

    def add(email: str) -> None:
        email = email.strip().lower()
        if email and _is_useful_email(email) and email not in out:
            out.append(email)

    for a in soup.select("a[href^='mailto:']"):
        add(a["href"][7:].split("?")[0])
    for match in _EMAIL_RE.findall(soup.get_text(" ", strip=True)):
        add(match)
    for email in decode_cf_emails(html):
        add(email)
    return out


# Facebook share/widget/tracking links that aren't the company's own page.
_FB_SKIP = ("sharer", "share.php", "/plugins/", "/dialog/", "facebook.com/tr", "/login", "/events/")


def _fb_has_handle(href: str) -> bool:
    tail = href.split("facebook.com/", 1)[-1].split("?")[0].strip("/")
    return bool(tail) and tail.lower() not in {"pages", "profile.php", "people"}


def extract_social_links(html: str) -> dict:
    """First Facebook + LinkedIn profile URL on the page (company pages, not widgets)."""
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        low = href.lower()
        if "facebook" not in out and "facebook.com/" in low:
            if not any(s in low for s in _FB_SKIP) and _fb_has_handle(href):
                out["facebook"] = href.split("?")[0]
        elif "linkedin" not in out and ("linkedin.com/company/" in low or "linkedin.com/in/" in low):
            out["linkedin"] = href.split("?")[0]
        if "facebook" in out and "linkedin" in out:
            break
    return out


def decode_cf_emails(html: str) -> list[str]:
    """Recover Cloudflare-obfuscated emails (``data-cfemail`` hex).

    Cloudflare replaces an email with a hex string whose first byte is an XOR
    key for the remaining bytes. Many directories (e.g. council member pages)
    hide emails this way, so decoding them keeps a real contact instead of the
    ``[email protected]`` placeholder.
    """
    out: list[str] = []
    for hexstr in _CF_EMAIL_RE.findall(html):
        try:
            raw = bytes.fromhex(hexstr)
            key = raw[0]
            email = "".join(chr(b ^ key) for b in raw[1:])
        except (ValueError, IndexError):
            continue
        if "@" in email and email not in out:
            out.append(email)
    return out
