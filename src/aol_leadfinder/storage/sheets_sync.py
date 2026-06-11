"""Append-only sync of NEW leads to the team's Google Sheet (the live CRM).

The sheet (default tab ``Sales_Review``) is a working CRM the sales team edits by
hand — call notes, contact status, follow-ups. So this NEVER clears or rewrites it:
it reads the phone/website keys already present, then **appends only leads that are
new**, leaving every existing row and every manual sales column untouched. Our new
data fields are added as extra columns at the END (after the manual columns).

Auth accepts either ``GOOGLE_SHEETS_CRED_JSON`` (the JSON content — for CI / the
autopilot) or ``GOOGLE_SHEETS_CRED`` (a file path — for local dev). gspread /
google-auth are imported lazily so the rest of the app runs without them.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import pandas as pd

from ..config import get_settings
from ..logging_setup import get_logger
from ..pipeline.normalize import normalize_domain

log = get_logger("sheets")

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# The 16 lead-owned columns we write, in the order the Sales_Review sheet uses.
# Everything after these (Sales Name … Notes) is MANUAL and never written here.
_LEAD_HEADER = [
    "Company", "Phone", "WhatsApp", "Extra Phones", "Email", "Website", "Category",
    "Type", "Intent", "Markets", "City", "Country", "Address", "Score", "Tier", "Status",
]
# New data columns appended at the very end (after the manual sales columns).
_NEW_COLUMNS = [
    "Facebook", "LinkedIn", "Product Type", "Store Platform",
    "Contact Name", "Contact Role", "Contact Email", "Segment", "Source", "Added Date",
]


class SheetsNotConfigured(RuntimeError):
    pass


@dataclass
class AppendResult:
    appended: int = 0
    skipped: int = 0
    leads: list = field(default_factory=list)  # the Lead objects that were appended
    url: Optional[str] = None


def is_configured() -> bool:
    """True when service-account credentials are available (either form)."""
    return bool(os.environ.get("GOOGLE_SHEETS_CRED_JSON")) or bool(
        os.environ.get("GOOGLE_SHEETS_CRED") and os.path.exists(os.environ["GOOGLE_SHEETS_CRED"])
    )


def _load_credentials():
    from google.oauth2.service_account import Credentials

    blob = os.environ.get("GOOGLE_SHEETS_CRED_JSON")
    if blob:
        return Credentials.from_service_account_info(json.loads(blob), scopes=_SCOPES)
    path = os.environ.get("GOOGLE_SHEETS_CRED")
    if path and os.path.exists(path):
        return Credentials.from_service_account_file(path, scopes=_SCOPES)
    raise SheetsNotConfigured(
        "Google Sheets not configured. Set GOOGLE_SHEETS_CRED_JSON (service-account JSON) "
        "or GOOGLE_SHEETS_CRED (path), and share the sheet with that account as Editor."
    )


def _wa_number(lead: Any) -> str:
    links = getattr(lead, "social_links", None) or {}
    wa = links.get("whatsapp")
    return wa.rsplit("/", 1)[-1] if wa else ""


def _join(value) -> str:
    return ", ".join(value) if isinstance(value, (list, tuple)) else ("" if value is None else str(value))


# header name -> value extractor. Used for the FIRST occurrence of each name only,
# so a duplicate header (the sheet has two "Status" columns) keeps the manual one blank.
_VALUE_BY_HEADER = {
    "Company": lambda L, today: getattr(L, "company_name", ""),
    "Phone": lambda L, today: getattr(L, "phone_e164", "") or "",
    "WhatsApp": lambda L, today: _wa_number(L),
    "Extra Phones": lambda L, today: _join(getattr(L, "extra_phones", None)),
    "Email": lambda L, today: getattr(L, "email", "") or "",
    "Website": lambda L, today: getattr(L, "website", "") or "",
    "Category": lambda L, today: getattr(L, "category", "") or "",
    "Type": lambda L, today: getattr(L, "company_type", "") or "",
    "Intent": lambda L, today: getattr(L, "shipping_intent", "") or "",
    "Markets": lambda L, today: _join(getattr(L, "target_markets", None)),
    "City": lambda L, today: getattr(L, "city", "") or "",
    "Country": lambda L, today: getattr(L, "country", "") or "",
    "Address": lambda L, today: getattr(L, "address", "") or "",
    "Score": lambda L, today: getattr(L, "score", "") if getattr(L, "score", None) is not None else "",
    "Tier": lambda L, today: getattr(L, "tier", "") or "",
    "Status": lambda L, today: "new",
    "Facebook": lambda L, today: getattr(L, "facebook", "") or "",
    "LinkedIn": lambda L, today: getattr(L, "linkedin", "") or "",
    "Product Type": lambda L, today: getattr(L, "product_type", "") or "",
    "Store Platform": lambda L, today: getattr(L, "store_platform", "") or "",
    "Contact Name": lambda L, today: getattr(L, "contact_name", "") or "",
    "Contact Role": lambda L, today: getattr(L, "contact_role", "") or "",
    "Contact Email": lambda L, today: getattr(L, "contact_email", "") or "",
    "Segment": lambda L, today: getattr(L, "segment", "") or "",
    "Source": lambda L, today: getattr(L, "source", "") or "",
    "Added Date": lambda L, today: today,
}


def _lead_keys(lead: Any) -> tuple[Optional[str], Optional[str]]:
    return getattr(lead, "phone_e164", None), getattr(lead, "domain", None)


def _map_row(lead: Any, header: list[str], today: str) -> list[str]:
    """Align one lead to the sheet's header. First occurrence of a known column is
    filled; manual columns and any duplicate header are left blank (never overwritten)."""
    used: set[str] = set()
    row: list[str] = []
    for h in header:
        if h in _VALUE_BY_HEADER and h not in used:
            used.add(h)
            val = _VALUE_BY_HEADER[h](lead, today)
            row.append("" if val is None else str(val))
        else:
            row.append("")
    return row


def _rows_to_append(leads, existing_keys: set, header: list[str], today: str):
    """Pure: pick leads that are new (not already pushed and not already in the sheet)
    and map them to header-aligned rows. Returns (rows, appended_leads, skipped)."""
    rows: list[list[str]] = []
    appended: list = []
    skipped = 0
    for lead in leads:
        if getattr(lead, "pushed_to_sheet", False):
            skipped += 1
            continue
        phone, domain = _lead_keys(lead)
        if (phone and phone in existing_keys) or (domain and domain in existing_keys):
            skipped += 1
            continue
        rows.append(_map_row(lead, header, today))
        appended.append(lead)
    return rows, appended, skipped


def _existing_keys(worksheet, header: list[str]) -> set:
    keys: set = set()
    if "Phone" in header:
        for v in worksheet.col_values(header.index("Phone") + 1)[1:]:
            v = (v or "").strip()
            if v:
                keys.add(v)
    if "Website" in header:
        for v in worksheet.col_values(header.index("Website") + 1)[1:]:
            d = normalize_domain(v)
            if d:
                keys.add(d)
    return keys


def _ensure_new_columns(worksheet, header: list[str]):
    """Append our new data columns once, at the END — never touching existing cells."""
    import gspread

    missing = [c for c in _NEW_COLUMNS if c not in header]
    if not missing:
        return header
    start = len(header) + 1
    rng = f"{gspread.utils.rowcol_to_a1(1, start)}:{gspread.utils.rowcol_to_a1(1, start + len(missing) - 1)}"
    worksheet.update(rng, [missing])
    return header + missing


def append_new_leads(leads, *, sheet_id: Optional[str] = None, tab: Optional[str] = None) -> AppendResult:
    """Append only NEW leads to the sheet (append-only; existing rows untouched)."""
    import gspread

    creds = _load_credentials()
    settings = get_settings()
    sheet_id = sheet_id or settings.sheet_id
    tab = tab or settings.sheet_tab
    if not sheet_id:
        raise SheetsNotConfigured("Set GOOGLE_SHEET_ID to the target spreadsheet id.")

    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)
    try:
        worksheet = spreadsheet.worksheet(tab)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=tab, rows=1000, cols=40)

    header = worksheet.row_values(1)
    if not header:
        header = _LEAD_HEADER + _NEW_COLUMNS
        worksheet.update("A1", [header])
    else:
        header = _ensure_new_columns(worksheet, header)

    existing = _existing_keys(worksheet, header)
    rows, appended, skipped = _rows_to_append(leads, existing, header, date.today().isoformat())
    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    log.info("appended %d new leads to '%s' (skipped %d already present)", len(rows), tab, skipped)
    return AppendResult(appended=len(rows), skipped=skipped, leads=appended, url=spreadsheet.url)


def push_dataframe(df: pd.DataFrame, sheet_name: Optional[str] = None) -> str:
    """DEPRECATED destructive overwrite (clears the sheet). Kept for the advanced
    'overwrite' action only — the autopilot/UI use append_new_leads instead."""
    creds = _load_credentials()
    import gspread

    sheet_name = sheet_name or os.environ.get("GOOGLE_SHEETS_NAME", "Air Ocean Leads")
    client = gspread.authorize(creds)
    try:
        spreadsheet = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(sheet_name)

    worksheet = spreadsheet.sheet1
    worksheet.clear()
    df = df.fillna("").astype(str)
    worksheet.update([df.columns.tolist()] + df.values.tolist())
    log.info("overwrote %d rows to Google Sheet '%s'", len(df), sheet_name)
    return spreadsheet.url
