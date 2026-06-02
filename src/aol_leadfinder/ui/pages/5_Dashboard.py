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

from aol_leadfinder.storage.db import read_all_leads, read_quarantined  # noqa: E402
from aol_leadfinder.storage.models import ENGAGED_STATUSES, STATUS_LABELS_AR  # noqa: E402
from aol_leadfinder.ui.common import get_ready_engine  # noqa: E402

st.set_page_config(page_title="Dashboard — Air Ocean Lead Finder", page_icon="📊", layout="wide")
st.title("📊 لوحة الإدارة / Dashboard")

engine = get_ready_engine()
leads = read_all_leads(engine)
if not leads:
    st.info("لسه مفيش عملاء. ابدأ بحث من صفحة **🔍 Search**.")
    st.stop()

total = len(leads)
today = _dt.date.today()
status_counts = {s: 0 for s in STATUS_LABELS_AR}
tier_counts = {"Hot": 0, "Medium": 0, "Weak": 0}
type_counts: dict[str, int] = {}
intent_vals: list[int] = []
engaged = won = due = 0
for lead in leads:
    status_counts[lead.status] = status_counts.get(lead.status, 0) + 1
    tier_counts[lead.tier] = tier_counts.get(lead.tier, 0) + 1
    if lead.company_type:
        type_counts[lead.company_type] = type_counts.get(lead.company_type, 0) + 1
    if lead.shipping_intent is not None:
        intent_vals.append(lead.shipping_intent)
    if lead.status in ENGAGED_STATUSES:
        engaged += 1
    if lead.status == "won":
        won += 1
    if (
        lead.next_followup_date is not None
        and lead.next_followup_date <= today
        and lead.status not in ("won", "lost")
    ):
        due += 1

conversion = (won / engaged * 100) if engaged else 0.0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("إجمالي العملاء", total)
c2.metric("🔴 Hot", tier_counts.get("Hot", 0))
c3.metric("تم التواصل", engaged)
c4.metric("تعاقد (Won)", won)
c5.metric("Conversion", f"{conversion:.0f}%")

if due:
    st.warning(f"⏰ عندك {due} متابعة مستحقّة النهاردة أو متأخرة — شوف صفحة Leads (فلتر 'متابعات مستحقّة').")

_quarantined = len(read_quarantined(engine))
if _quarantined:
    st.caption(f"🚧 {_quarantined} سجل في المراجعة (Quarantine) — مستبعد من الأرقام دي. شوفهم في صفحة Leads.")

st.divider()
col_a, col_b = st.columns(2)
with col_a:
    st.subheader("حسب المرحلة / By stage")
    stage_df = pd.DataFrame(
        {"المرحلة": [STATUS_LABELS_AR[s] for s in STATUS_LABELS_AR], "العدد": [status_counts[s] for s in STATUS_LABELS_AR]}
    ).set_index("المرحلة")
    st.bar_chart(stage_df)
with col_b:
    st.subheader("حسب الجودة / By tier")
    tier_df = pd.DataFrame(
        {"Tier": list(tier_counts.keys()), "العدد": list(tier_counts.values())}
    ).set_index("Tier")
    st.bar_chart(tier_df)

if type_counts:
    st.divider()
    st.subheader("ذكاء الشركات / Company Intelligence")
    ci1, ci2 = st.columns([1, 2])
    avg_intent = sum(intent_vals) / len(intent_vals) if intent_vals else 0
    ci1.metric("متوسط نية الشحن / Avg shipping intent", f"{avg_intent:.0f}/100")
    type_df = pd.DataFrame(
        {"النوع": list(type_counts.keys()), "العدد": list(type_counts.values())}
    ).set_index("النوع")
    ci2.bar_chart(type_df)
