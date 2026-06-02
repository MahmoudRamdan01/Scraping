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

from aol_leadfinder.storage.db import read_all_leads, read_quarantined, read_runs  # noqa: E402
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

# ---- Source Health (Sprint A observability) ----
st.divider()
st.subheader("صحة المصادر / Source Health")
st.caption("آخر 100 تشغيل — Yield = عدد العملاء المقبولين من كل مصدر / kept per source over the last 100 runs")

_HEALTH_BADGE = {"ok": "🟢 ok", "empty": "🟡 empty", "blocked": "🔴 blocked", "error": "🔴 error"}
_src_rows: dict[str, dict] = {}
for _run in read_runs(engine, limit=100):  # newest first
    _when = _run.finished_at or _run.started_at
    for _key, _s in (_run.source_stats or {}).items():
        _row = _src_rows.get(_key)
        if _row is None:  # first (newest) sighting sets current health + last run
            _row = {"source": _key, "health": _s.get("health", "—"),
                    "yield": 0, "last_success": None, "last_run": _when}
            _src_rows[_key] = _row
        _row["yield"] += int(_s.get("kept", 0) or 0)
        if _row["last_success"] is None and int(_s.get("found", 0) or 0) > 0:
            _row["last_success"] = _when


def _fmt_dt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if isinstance(value, _dt.datetime) else "—"


if not _src_rows:
    st.caption("لسه مفيش بيانات per-source — هتتسجّل تلقائيًا بعد أول بحث.")
else:
    health_df = pd.DataFrame(
        [
            {
                "المصدر / Source": r["source"],
                "الحالة / Health": _HEALTH_BADGE.get(r["health"], r["health"]),
                "Yield (kept)": r["yield"],
                "آخر نجاح / Last success": _fmt_dt(r["last_success"]),
                "آخر تشغيل / Last run": _fmt_dt(r["last_run"]),
            }
            for r in _src_rows.values()
        ]
    ).sort_values("المصدر / Source").set_index("المصدر / Source")
    st.dataframe(health_df, use_container_width=True)

    _bad = [r["source"] for r in _src_rows.values() if r["health"] in ("blocked", "error")]
    _empty = [r["source"] for r in _src_rows.values() if r["health"] == "empty"]
    if _bad:
        st.error("🔴 مصادر فيها مشكلة في آخر تشغيل / failing: " + "، ".join(_bad))
    if _empty:
        st.warning("🟡 مصادر رجّعت صفر في آخر تشغيل / empty: " + "، ".join(_empty))

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
