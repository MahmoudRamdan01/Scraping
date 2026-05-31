from __future__ import annotations

import datetime as _dt
import pathlib
import sys

for _p in pathlib.Path(__file__).resolve().parents:
    if _p.name == "src" and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
        break

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from aol_leadfinder.pipeline.score import format_reasons  # noqa: E402
from aol_leadfinder.storage.db import read_all_leads, update_lead_crm  # noqa: E402
from aol_leadfinder.storage.models import STATUS_LABELS_AR  # noqa: E402
from aol_leadfinder.ui.common import get_ready_engine  # noqa: E402

_AR_TO_STATUS = {v: k for k, v in STATUS_LABELS_AR.items()}
_STATUS_LABELS = list(STATUS_LABELS_AR.values())


def _coerce_date(value):
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


st.set_page_config(page_title="Leads — Air Ocean Lead Finder", page_icon="📋", layout="wide")
st.title("📋 العملاء / Leads (CRM)")

engine = get_ready_engine()
leads = read_all_leads(engine)

if not leads:
    st.info("لسه مفيش عملاء. روح صفحة **🔍 Search** وابدأ بحث.")
    st.stop()

today = _dt.date.today()
rows = []
for lead in leads:
    rows.append(
        {
            "id": lead.id,
            "Company": lead.company_name,
            "Phone": lead.phone_e164,
            "City": lead.city,
            "Category": lead.category,
            "Score": lead.score,
            "Tier": lead.tier,
            "Why": format_reasons(lead.score_reasons),
            "Type": lead.company_type or "",
            "Intent": lead.shipping_intent,
            "Status": STATUS_LABELS_AR.get(lead.status, lead.status),
            "Assigned To": lead.assigned_to or "",
            "Last Contact": lead.last_contact_date,
            "Next Follow-up": lead.next_followup_date,
            "Notes": lead.notes or "",
        }
    )
df = pd.DataFrame(rows)

# ---- Filters ----
f1, f2, f3, f4 = st.columns([1, 1, 1, 1])
tier_filter = f1.multiselect("Tier", ["Hot", "Medium", "Weak"], default=["Hot", "Medium", "Weak"])
status_filter = f2.multiselect("Status", _STATUS_LABELS, default=_STATUS_LABELS)
assigned_filter = f3.text_input("Assigned To")
due_only = f4.checkbox("متابعات مستحقّة فقط")

view = df[df["Tier"].isin(tier_filter) & df["Status"].isin(status_filter)]
if assigned_filter:
    view = view[view["Assigned To"].str.contains(assigned_filter, case=False, na=False)]
search_text = st.text_input("بحث بالاسم / Search company")
if search_text:
    view = view[view["Company"].str.contains(search_text, case=False, na=False)]
if due_only:
    open_status = {STATUS_LABELS_AR["won"], STATUS_LABELS_AR["lost"]}
    mask = view["Next Follow-up"].apply(
        lambda d: _coerce_date(d) is not None and _coerce_date(d) <= today
    )
    view = view[mask & ~view["Status"].isin(open_status)]

st.caption(f"{len(view)} من {len(df)} عميل")

edited = st.data_editor(
    view,
    hide_index=True,
    use_container_width=True,
    column_config={
        "id": None,
        "Why": st.column_config.TextColumn("Why", help="ليه السكور ده؟"),
        "Score": st.column_config.NumberColumn("Score"),
        "Intent": st.column_config.NumberColumn("Intent", help="نية الشحن 0-100"),
        "Status": st.column_config.SelectboxColumn("Status", options=_STATUS_LABELS),
        "Last Contact": st.column_config.DateColumn("Last Contact"),
        "Next Follow-up": st.column_config.DateColumn("Next Follow-up"),
    },
    disabled=["Company", "Phone", "City", "Category", "Score", "Tier", "Why", "Type", "Intent"],
    key="leads_editor",
)

if st.button("💾 حفظ التعديلات / Save changes", type="primary"):
    n = 0
    for _, r in edited.iterrows():
        ok = update_lead_crm(
            engine,
            int(r["id"]),
            status=_AR_TO_STATUS.get(r["Status"], "new"),
            assigned_to=(r["Assigned To"] or None),
            last_contact_date=_coerce_date(r["Last Contact"]),
            next_followup_date=_coerce_date(r["Next Follow-up"]),
            notes=(r["Notes"] or None),
        )
        n += int(ok)
    st.success(f"اتحفظ {n} عميل.")
