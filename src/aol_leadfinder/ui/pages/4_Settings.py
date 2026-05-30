from __future__ import annotations

import pathlib
import sys

for _p in pathlib.Path(__file__).resolve().parents:
    if _p.name == "src" and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
        break

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
import yaml  # noqa: E402

from aol_leadfinder.config import (  # noqa: E402
    get_categories,
    get_filters,
    get_scoring,
    get_settings,
    get_sources,
)

st.set_page_config(page_title="Settings — Air Ocean Lead Finder", page_icon="⚙️", layout="wide")
st.title("⚙️ الإعدادات / Settings")

settings = get_settings()

# ---- Categories (with add form) ----
st.subheader("المجالات / Categories")
categories = get_categories()
st.dataframe(
    pd.DataFrame([{"Category": c["name"], "Keywords": ", ".join(c.get("keywords", []))} for c in categories]),
    use_container_width=True,
    hide_index=True,
)

with st.form("add_category"):
    st.markdown("**➕ ضيف مجال جديد**")
    new_name = st.text_input("الاسم / Name")
    new_keywords = st.text_input("كلمات مفتاحية (مفصولة بفاصلة) / Keywords (comma-separated)")
    submitted = st.form_submit_button("إضافة / Add")
    if submitted and new_name.strip():
        path = settings.config_dir / "categories.yaml"
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        data.setdefault("categories", []).append(
            {"name": new_name.strip(), "keywords": [k.strip() for k in new_keywords.split(",") if k.strip()]}
        )
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
        st.success(f"تمت إضافة '{new_name.strip()}'. حدّث الصفحة.")

st.divider()

# ---- Sources ----
st.subheader("المصادر / Sources")
src_rows = [
    {
        "key": key,
        "label": meta.get("label", key),
        "tier": meta.get("tier"),
        "enabled": meta.get("enabled", False),
        "flag": meta.get("requires_flag", ""),
    }
    for key, meta in get_sources().items()
]
st.dataframe(pd.DataFrame(src_rows), use_container_width=True, hide_index=True)
st.caption("🟢 green = سهل ومتوافق · 🟡 yellow = صعب (Phase 2) · 🔴 deferred = خطر ToS/قانوني (OFF)")

# ---- Feature flags ----
st.subheader("Feature flags (DEFERRED / RED-zone)")
flags = ["FEATURE_FACEBOOK", "FEATURE_INSTAGRAM", "FEATURE_LINKEDIN", "FEATURE_TRUECALLER"]
flag_rows = [{"flag": f, "enabled": settings.feature_flag(f)} for f in flags]
st.dataframe(pd.DataFrame(flag_rows), use_container_width=True, hide_index=True)
if any(r["enabled"] for r in flag_rows):
    st.error(
        "⚠️ في مصدر DEFERRED مفعّل. دي مصادر بتخالف شروط المنصات وممكن تصادم قانون البيانات — "
        "استخدمها على مسؤوليتك. تتظبط من ملف .env."
    )
else:
    st.success("كل المصادر الخطرة متوقفة (الوضع الآمن).")

st.divider()

# ---- Filters & scoring (read-only view) ----
col_a, col_b = st.columns(2)
with col_a:
    st.subheader("الفلاتر / Filters")
    st.json(get_filters())
    st.caption("للتعديل: عدّل config/filters.yaml")
with col_b:
    st.subheader("التقييم / Scoring")
    st.json(get_scoring())
    st.caption("للتعديل: عدّل config/scoring.yaml")
