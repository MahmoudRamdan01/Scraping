"""Structural validation gate (pipeline/validate.py)."""
from aol_leadfinder.pipeline.normalize import normalize_lead
from aol_leadfinder.pipeline.validate import validate_lead
from aol_leadfinder.scrapers.base import RawLead


def _norm(**kw):
    return normalize_lead(RawLead(source="egydir", **kw))


def test_valid_with_phone():
    ok, reason = validate_lead(_norm(company_name="Acme Foods", phone_raw="01012345678"))
    assert ok and reason is None


def test_valid_with_only_website():
    ok, reason = validate_lead(_norm(company_name="Acme Foods", website="acme.example"))
    assert ok and reason is None


def test_no_identity():
    ok, reason = validate_lead(_norm(company_name="", phone_raw="01012345678"))
    assert not ok and reason == "no_identity"


def test_junk_name_checked_before_contact():
    # Has a valid phone, but the name is junk -> junk_name wins (ordered first).
    ok, reason = validate_lead(_norm(company_name="--", phone_raw="01012345678"))
    assert not ok and reason == "junk_name"


def test_no_contact():
    ok, reason = validate_lead(_norm(company_name="Acme Foods"))
    assert not ok and reason == "no_contact"


def test_bad_phone_shape_is_defensive():
    # normalize would null a bad number, so feed a raw object to exercise the guard.
    class L:
        company_name = "Acme Foods"
        phone_e164 = "0123"  # missing + / not E.164
        email = website = domain = None

    ok, reason = validate_lead(L())
    assert not ok and reason == "bad_phone"
