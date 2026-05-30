from __future__ import annotations

import pathlib
import sys

for _p in pathlib.Path(__file__).resolve().parents:
    if _p.name == "src" and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
        break

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from aol_leadfinder.storage.db import read_all_leads, update_lead_status  # noqa: E402
from aol_leadfinder.storage.models import LEAD_STATUSES  # noqa: E402
from aol_leadfinder.ui.common import get_ready_engine  # noqa: E402

st.set_page_config(page_title="Leads — Air Ocean Lead Finder", page_icon="📋", layout="wide")
st.title("📋 العملاء / Leads")

engine = get_ready_engine()
leads = read_all_leads(engine)

if not leads:
    st.info("لسه مفيش عملاء. روح صفحة **🔍 Search** وابدأ بحث.")
    st.stop()

rows = [
    {
        "id": lead.id,
        "Company": lead.company_name,
        "Phone": lead.phone_e164,
        "City": lead.city,
        "Category": lead.category,
        "Score": lead.score,
        "Tier": lead.tier,
        "Status": lead.status,
        "Website": lead.website,
        "Source": lead.source,
        "Notes": lead.notes or "",
    }
    for lead in leads
]
df = pd.DataFrame(rows)

f1, f2, f3 = st.columns([1, 1, 2])
tier_filter = f1.multiselect("Tier", ["Hot", "Medium", "Weak"], default=["Hot", "Medium", "Weak"])
status_filter = f2.multiselect("Status", LEAD_STATUSES, default=LEAD_STATUSES)
search_text = f3.text_input("بحث بالاسم / Search company")

view = df[df["Tier"].isin(tier_filter) & df["Status"].isin(status_filter)]
if search_text:
    view = view[view["Company"].str.contains(search_text, case=False, na=False)]

st.caption(f"{len(view)} من {len(df)} عميل")

edited = st.data_editor(
    view,
    hide_index=True,
    use_container_width=True,
    column_config={
        "id": None,
        "Status": st.column_config.SelectboxColumn("Status", options=LEAD_STATUSES),
        "Score": st.column_config.NumberColumn("Score", disabled=True),
        "Website": st.column_config.LinkColumn("Website"),
    },
    disabled=["Company", "Phone", "City", "Category", "Score", "Tier", "Source"],
    key="leads_editor",
)

if st.button("💾 حفظ التعديلات / Save changes"):
    n = 0
    for _, r in edited.iterrows():
        if update_lead_status(engine, int(r["id"]), status=r["Status"], notes=r["Notes"]):
            n += 1
    st.success(f"اتحفظ {n} عميل.")
