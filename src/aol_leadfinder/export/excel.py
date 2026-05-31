"""Excel export. Turns Lead rows into a tidy, sales-ready spreadsheet."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

# (attribute, column header) in display order
_COLUMNS = [
    ("company_name", "Company"),
    ("phone_e164", "Phone"),
    ("extra_phones", "Extra Phones"),
    ("email", "Email"),
    ("website", "Website"),
    ("category", "Category"),
    ("company_type", "Type"),
    ("shipping_intent", "Shipping Intent"),
    ("city", "City"),
    ("governorate", "Governorate"),
    ("country", "Country"),
    ("address", "Address"),
    ("followers", "Followers"),
    ("last_activity_date", "Last Activity"),
    ("rating", "Rating"),
    ("score", "Score"),
    ("tier", "Tier"),
    ("status", "Status"),
    ("assigned_to", "Assigned To"),
    ("next_followup_date", "Next Follow-up"),
    ("source", "Source"),
    ("source_url", "Source URL"),
]


def leads_to_dataframe(leads: Iterable) -> pd.DataFrame:
    rows = []
    for lead in leads:
        row = {}
        for attr, header in _COLUMNS:
            val = getattr(lead, attr, None)
            if attr == "extra_phones" and isinstance(val, list):
                val = ", ".join(val)
            row[header] = val
        rows.append(row)
    return pd.DataFrame(rows, columns=[h for _, h in _COLUMNS])


def export_excel(leads: Iterable, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = leads_to_dataframe(leads)
    df.to_excel(path, index=False, engine="openpyxl")
    return path
