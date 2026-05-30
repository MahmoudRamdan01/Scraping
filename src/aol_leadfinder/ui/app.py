"""Air Ocean Lead Finder — Streamlit home page.

Run with:  streamlit run src/aol_leadfinder/ui/app.py
"""
from __future__ import annotations

import pathlib
import sys

# Make the package importable whether or not it's pip-installed.
for _p in pathlib.Path(__file__).resolve().parents:
    if _p.name == "src" and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
        break

import streamlit as st  # noqa: E402

from aol_leadfinder.storage.db import read_all_leads  # noqa: E402
from aol_leadfinder.ui.common import get_ready_engine  # noqa: E402

st.set_page_config(page_title="Air Ocean Lead Finder", page_icon="🚢", layout="wide")

st.title("🚢 Air Ocean Lead Finder")
st.caption("أداة Lead Generation لشركة Air Ocean Line — بيانات شركات عامة، تقييم، وتصدير Excel/Sheets.")

st.info(
    "ℹ️ **النسخة الحالية (v1):** بتجمع بيانات شركات **منشورة للعامة** من أدلة الأعمال، "
    "بتفلترها وتقيّمها، وبتطلعها Excel / Google Sheet. **المراسلة يدوية** (مفيش إرسال آلي) "
    "للالتزام بقانون البيانات. مصادر السوشيال/Truecaller متوقفة by default."
)

engine = get_ready_engine()
leads = read_all_leads(engine)
by_tier = {"Hot": 0, "Medium": 0, "Weak": 0}
for lead in leads:
    by_tier[lead.tier] = by_tier.get(lead.tier, 0) + 1

c1, c2, c3, c4 = st.columns(4)
c1.metric("إجمالي العملاء / Total", len(leads))
c2.metric("🔴 Hot", by_tier.get("Hot", 0))
c3.metric("🟡 Medium", by_tier.get("Medium", 0))
c4.metric("⚪ Weak", by_tier.get("Weak", 0))

st.divider()
st.subheader("الخطوات / How to use")
st.markdown(
    """
1. **🔍 Search** — اختار الدولة/المدينة/المجال والمصادر، ودوس *ابدأ البحث*.
2. **📋 Leads** — شوف العملاء مرتبين بالـ Score، فلترهم، وحدّث حالة كل عميل (تم التواصل / تفاوض / تعاقد).
3. **📤 Export** — نزّل Excel أو زامن مع Google Sheet عشان مستر زياد يتابع.
4. **⚙️ Settings** — ضيف مجالات جديدة، وشوف المصادر والفلاتر والتقييم.

استخدم القائمة الجانبية للتنقل بين الصفحات.
"""
)
