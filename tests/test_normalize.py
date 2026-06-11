from aol_leadfinder.pipeline.normalize import (
    _clean_email,
    normalize_domain,
    normalize_lead,
    normalize_name,
    normalize_phone,
)
from aol_leadfinder.scrapers.base import RawLead


def test_clean_email_fixes_real_world_breakage():
    assert _clean_email("INFO@Nile.example") == "info@nile.example"
    assert _clean_email("%20info@makkacorp.com") == "info@makkacorp.com"   # url-encoded space
    assert _clean_email("sales@dubaigateeg.com.com") == "sales@dubaigateeg.com"  # doubled TLD
    assert _clean_email("cs@ecc.com | export@ecc-eg.net") == "cs@ecc.com"   # multi-email cell
    assert _clean_email("noreply@x.com") is None                            # role junk
    assert _clean_email("not-an-email") is None
    assert _clean_email(None) is None


def test_normalize_phone_egyptian_formats():
    assert normalize_phone("+20 100 123 4567", "EG") == "+201001234567"
    assert normalize_phone("01012345678", "EG") == "+201012345678"


def test_normalize_phone_invalid():
    assert normalize_phone(None) is None
    assert normalize_phone("") is None
    assert normalize_phone("hello") is None
    assert normalize_phone("123", "EG") is None


def test_normalize_domain():
    assert normalize_domain("https://www.Example.com/path?x=1") == "example.com"
    assert normalize_domain("example.com") == "example.com"
    assert normalize_domain("HTTP://Sub.Site.CO/") == "sub.site.co"
    assert normalize_domain(None) is None


def test_normalize_name():
    assert normalize_name("  Nile   Beauty!! ") == "nile beauty"
    assert normalize_name(None) == ""


def test_normalize_lead_fills_canonical_fields():
    raw = RawLead(
        company_name="  Nile Beauty  ",
        source="egydir",
        phone_raw="01012345678",
        extra_phones=["+20 100 123 4567", "garbage"],
        email="INFO@Nile.example",
        website="nile.example",
    )
    n = normalize_lead(raw, default_country="Egypt", region="EG")
    assert n.company_name == "Nile Beauty"
    assert n.company_name_norm == "nile beauty"
    assert n.phone_e164 == "+201012345678"
    assert "+201001234567" in n.extra_phones
    assert n.email == "info@nile.example"
    assert n.domain == "nile.example"
    assert n.website.startswith("https://")
    assert n.country == "Egypt"
