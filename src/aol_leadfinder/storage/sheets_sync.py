"""Optional one-way sync of leads to a free Google Sheet (manager visibility).

Requires a Google service-account JSON key (GOOGLE_SHEETS_CRED) and the target
sheet shared with the service-account email. gspread/google-auth are imported
lazily so the rest of the app runs without them installed.
"""
from __future__ import annotations

import os

import pandas as pd

from ..logging_setup import get_logger

log = get_logger("sheets")


class SheetsNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    cred = os.environ.get("GOOGLE_SHEETS_CRED", "")
    return bool(cred) and os.path.exists(cred)


def push_dataframe(df: pd.DataFrame, sheet_name: str | None = None) -> str:
    if not is_configured():
        raise SheetsNotConfigured(
            "Google Sheets not configured. Set GOOGLE_SHEETS_CRED in .env to a valid "
            "service-account JSON path and share the sheet with that account."
        )
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:  # pragma: no cover
        raise SheetsNotConfigured("Install extras: pip install gspread google-auth") from exc

    sheet_name = sheet_name or os.environ.get("GOOGLE_SHEETS_NAME", "Air Ocean Leads")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(os.environ["GOOGLE_SHEETS_CRED"], scopes=scopes)
    client = gspread.authorize(creds)

    try:
        spreadsheet = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(sheet_name)

    worksheet = spreadsheet.sheet1
    worksheet.clear()
    df = df.fillna("").astype(str)
    worksheet.update([df.columns.tolist()] + df.values.tolist())
    log.info("synced %d rows to Google Sheet '%s'", len(df), sheet_name)
    return spreadsheet.url
