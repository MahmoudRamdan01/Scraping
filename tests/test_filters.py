from datetime import date

from aol_leadfinder.pipeline.filters import passes_filters
from aol_leadfinder.pipeline.normalize import normalize_lead
from aol_leadfinder.scrapers.base import RawLead

FCFG = {
    "activity": {"enabled": True, "drop_if_year_at_or_before": 2023, "drop_if_activity_unknown": False},
    "followers": {"enabled": True, "min": 1000},
    "require_phone": True,
    "require_website": True,
}


def _lead(**kwargs):
    base = dict(company_name="X", source="egydir", phone_raw="01012345678", website="x.example")
    base.update(kwargs)
    return normalize_lead(RawLead(**base))


def test_passes_when_all_good():
    lead = _lead(followers=2000, last_activity_date=date.today())
    ok, reason = passes_filters(lead, FCFG)
    assert ok and reason is None


def test_drop_no_phone():
    lead = _lead(phone_raw=None, followers=2000, last_activity_date=date.today())
    assert passes_filters(lead, FCFG) == (False, "no_phone")


def test_drop_no_website():
    lead = _lead(website=None, followers=2000, last_activity_date=date.today())
    assert passes_filters(lead, FCFG) == (False, "no_website")


def test_drop_inactive():
    lead = _lead(followers=2000, last_activity_date=date(2021, 6, 1))
    assert passes_filters(lead, FCFG) == (False, "inactive")


def test_drop_low_followers():
    lead = _lead(followers=50, last_activity_date=date.today())
    assert passes_filters(lead, FCFG) == (False, "low_followers")


def test_keep_when_followers_unknown():
    lead = _lead(followers=None, last_activity_date=date.today())
    ok, _ = passes_filters(lead, FCFG)
    assert ok
