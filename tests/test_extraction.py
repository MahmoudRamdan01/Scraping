"""Quality-first phone/email extraction (the fix for missing/wrong contacts)."""
from aol_leadfinder.scrapers.http import (
    best_e164,
    extract_emails_from_html,
    extract_phone_from_html,
    extract_phones,
    extract_whatsapp_numbers,
)


def test_best_e164_validates():
    assert best_e164("+20 100 123 4567", "EG") == "+201001234567"
    assert best_e164("0100 123 4567", "EG") == "+201001234567"
    assert best_e164("123", "EG") is None          # too short -> rejected
    assert best_e164("not a phone", "EG") is None


def test_extract_phones_skips_junk_first_number():
    # A tax id / random figure appears BEFORE the real phone in the text.
    html = (
        "<html><body>"
        "<p>Tax ID 12345 — established 2009</p>"
        "<a href='tel:+201001234567'>call us</a>"
        "</body></html>"
    )
    phones = extract_phones(html, "EG")
    assert phones == ["+201001234567"]  # the tax id (invalid) is dropped


def test_whatsapp_prioritized_and_detected():
    html = (
        "<html><body>"
        "<a href='tel:+20226785885'>landline</a>"
        "<a href='https://wa.me/201001234567'>WhatsApp</a>"
        "</body></html>"
    )
    phones = extract_phones(html, "EG")
    assert phones[0] == "+201001234567"            # WhatsApp number ranked first
    assert "+20226785885" in phones                # landline still captured
    assert extract_whatsapp_numbers(html, "EG") == ["+201001234567"]


def test_extract_multiple_phones():
    html = (
        "<html><body>"
        "<a href='tel:+201001234567'>m</a>"
        "<a href='tel:+201112223334'>m2</a>"
        "</body></html>"
    )
    assert set(extract_phones(html, "EG")) == {"+201001234567", "+201112223334"}


def test_email_junk_filtered():
    html = (
        "<html><body>"
        "<a href='mailto:sales@realco.com'>e</a>"
        "<a href='mailto:noreply@realco.com'>x</a>"
        "logo@2x.png test@example.com"
        "</body></html>"
    )
    emails = extract_emails_from_html(html)
    assert "sales@realco.com" in emails
    assert "noreply@realco.com" not in emails       # noreply dropped
    assert all("example.com" not in e for e in emails)
    assert all(not e.endswith(".png") for e in emails)


def test_single_best_phone():
    html = "<a href='tel:+201001234567'>x</a>"
    assert extract_phone_from_html(html, "EG") == "+201001234567"
