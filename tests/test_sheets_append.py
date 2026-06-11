"""Append-only sheet sync — the pure row-mapping + dedup logic (no network).

Guards the two properties that protect the team's live CRM:
1. only genuinely-new leads become rows;
2. manual sales columns (and the sheet's duplicate "Status") are never written.
"""
from aol_leadfinder.storage.models import Lead
from aol_leadfinder.storage.sheets_sync import _map_row, _rows_to_append

# The real Sales_Review header: 16 lead columns, 8 manual columns (note the SECOND
# "Status"), then our appended data columns.
HEADER = [
    "Company", "Phone", "WhatsApp", "Extra Phones", "Email", "Website", "Category",
    "Type", "Intent", "Markets", "City", "Country", "Address", "Score", "Tier", "Status",
    "Sales Name", "Contact Status", "Contact Date", "Call Duration", "Status",
    "Follow Up", "Follow Up Date", "Notes",
    "Facebook", "LinkedIn", "Product Type", "Store Platform", "Contact Name",
    "Contact Role", "Contact Email", "Segment", "Source", "Added Date",
]


def _lead(**kw):
    base = dict(company_name="Acme", company_name_norm="acme")
    base.update(kw)
    return Lead(**base)


def test_map_row_fills_lead_columns_and_leaves_manual_blank():
    lead = _lead(
        phone_e164="+201001234567", website="https://acme.example", domain="acme.example",
        company_type="Manufacturer", score=88, tier="Hot", segment="P1",
        facebook="https://facebook.com/acme", contact_role="Export Manager", source="google_maps",
    )
    row_list = _map_row(lead, HEADER, "2026-06-11")
    row = dict(zip(HEADER, row_list))  # note: collapses the duplicate "Status" key

    assert row["Company"] == "Acme"
    assert row["Phone"] == "+201001234567"
    assert row_list[HEADER.index("Status")] == "new"   # first Status = lead status
    assert row["Score"] == "88" and row["Tier"] == "Hot"
    assert row["Facebook"] == "https://facebook.com/acme"
    assert row["Contact Role"] == "Export Manager"
    assert row["Segment"] == "P1" and row["Source"] == "google_maps"
    assert row["Added Date"] == "2026-06-11"
    # manual sales columns are never written
    for manual in ("Sales Name", "Contact Status", "Call Duration", "Follow Up", "Notes"):
        assert row[manual] == ""


def test_map_row_duplicate_status_only_first_is_filled():
    # The sheet has two "Status" columns; only the first (lead) one is written.
    row = _map_row(_lead(), HEADER, "2026-06-11")
    status_positions = [i for i, h in enumerate(HEADER) if h == "Status"]
    assert row[status_positions[0]] == "new"
    assert row[status_positions[1]] == ""   # the manual sales "Status" stays blank


def test_rows_to_append_skips_existing_and_pushed():
    existing = {"+201111111111", "existing.example"}
    leads = [
        _lead(company_name="New", phone_e164="+201002223334", domain="new.example"),
        _lead(company_name="DupPhone", phone_e164="+201111111111"),
        _lead(company_name="DupDomain", domain="existing.example"),
        _lead(company_name="Already", phone_e164="+201009998887", pushed_to_sheet=True),
    ]
    rows, appended, skipped = _rows_to_append(leads, existing, HEADER, "2026-06-11")

    assert len(rows) == 1
    assert appended[0].company_name == "New"
    assert skipped == 3


def test_rows_to_append_empty_when_all_known():
    existing = {"+201002223334"}
    leads = [_lead(phone_e164="+201002223334", domain="x.example")]
    rows, appended, skipped = _rows_to_append(leads, existing, HEADER, "2026-06-11")
    assert rows == [] and appended == [] and skipped == 1
