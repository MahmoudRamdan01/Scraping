from __future__ import annotations

import pathlib
import sys

for _p in pathlib.Path(__file__).resolve().parents:
    if _p.name == "src" and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
        break

import streamlit as st  # noqa: E402

from aol_leadfinder.config import get_categories  # noqa: E402
from aol_leadfinder.core.orchestrator import run_search  # noqa: E402
from aol_leadfinder.scrapers import registry  # noqa: E402
from aol_leadfinder.scrapers.base import SearchRequest  # noqa: E402

st.set_page_config(page_title="Search — Air Ocean Lead Finder", page_icon="🔍", layout="wide")
st.title("🔍 بحث / Search")

st.warning(
    "التشغيل بيفتح المصادر من جهازك بإيقاع بشري (delays) عشان ميتحظرش — فممكن ياخد وقت. "
    "كل النتائج بتتخزن وبتتفلتر وبتتقيّم تلقائيًا."
)

categories = get_categories()
category_names = [c["name"] for c in categories]

# Business role — turns a category into an End-Customer query
# (e.g. Cosmetics + Manufacturer -> "Cosmetics manufacturers in Cairo").
ROLES = ["Manufacturer", "Factory", "Importer", "Exporter", "Distributor", "Wholesaler", "Supplier", "(أي)"]

col1, col2, col3, col4 = st.columns(4)
country = col1.text_input("Country / الدولة", "Egypt")
city = col2.text_input("City / المدينة / المحافظة", "Cairo")
category = col3.selectbox("Category / المجال", category_names)
role = col4.selectbox("Business Role / نوع النشاط", ROLES, index=0)
max_results = st.slider("أقصى عدد نتائج لكل مصدر / Max results per source", 10, 500, 100, 10)
st.caption(
    "💡 لاستهداف **العملاء النهائيين**: استخدم Google Maps مع Category + Role "
    "(مثال: Cosmetics + Manufacturer في Cairo). أدلة الشحن للشراكات (Forwarders)."
)
enrich = st.checkbox(
    "🔎 حلّل مواقع الشركات (Company Intelligence) — أبطأ، بيقيّم نوع الشركة ونية الشحن",
    value=False,
)

sources = registry.available_sources()
if not sources:
    st.error("مفيش مصادر مفعّلة. راجع config/sources.yaml.")
    st.stop()

labels = {key: meta.get("label", key) for key, meta in sources.items()}
non_dummy = [k for k in sources if k != "dummy"]
selected = st.multiselect(
    "Sources / المصادر",
    options=list(sources.keys()),
    default=non_dummy or list(sources.keys()),
    format_func=lambda k: labels.get(k, k),
)

if st.button("🚀 ابدأ البحث / Run", type="primary"):
    if not selected:
        st.error("اختار مصدر واحد على الأقل.")
        st.stop()
    keywords = next((c.get("keywords", []) for c in categories if c["name"] == category), [])
    req = SearchRequest(
        country=country, city=city, category=category,
        role=(None if role == "(أي)" else role),
        keywords=keywords, max_results=max_results, enrich_websites=enrich,
    )
    with st.spinner("بنجمع الداتا ونفلترها ونقيّمها..."):
        stats = run_search(req, selected)

    st.success(
        f"تم ✅  لقينا {stats.found} | احتفظنا بـ {stats.kept} "
        f"(جديد {stats.created}, محدّث {stats.updated}) | استبعدنا {stats.dropped}"
    )
    if stats.drop_reasons:
        st.write("**أسباب الاستبعاد:**", stats.drop_reasons)
    if stats.errors:
        st.error(f"مصادر فشلت: {stats.errors}")
    st.info("افتح صفحة **📋 Leads** من القائمة الجانبية لرؤية النتائج وتحديث الحالات.")
