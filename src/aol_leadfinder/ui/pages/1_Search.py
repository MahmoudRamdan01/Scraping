from __future__ import annotations

import itertools
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
ROLES = ["Manufacturer", "Factory", "Importer", "Exporter", "Distributor", "Wholesaler", "Supplier"]

# Option lists for the multi-selects. Egypt-focused: the 27 governorates plus the
# key industrial cities where manufacturers cluster (the B1 location filter
# matches a lead's city OR governorate, so either works).
COUNTRIES = ["Egypt", "Saudi Arabia", "United Arab Emirates", "Kuwait", "Qatar", "Jordan", "Libya", "Sudan"]
GOVERNORATES = [
    "Cairo", "Giza", "Alexandria", "Qalyubia", "Dakahlia", "Sharqia", "Gharbia",
    "Monufia", "Beheira", "Kafr El Sheikh", "Damietta", "Port Said", "Ismailia",
    "Suez", "Faiyum", "Beni Suef", "Minya", "Asyut", "Sohag", "Qena", "Luxor",
    "Aswan", "Red Sea", "Matrouh", "North Sinai", "South Sinai", "New Valley",
    "6th of October", "10th of Ramadan", "Sadat City", "Borg El Arab",
]
MAX_COMBINATIONS = 120  # guard against an accidental cartesian explosion

st.caption(
    "اختار **أكتر من واحد** في أي خانة — هنبحث كل التوليفات / "
    "pick multiple in any field — every combination is searched."
)
col1, col2, col3, col4 = st.columns(4)
countries = col1.multiselect("Country / الدولة", COUNTRIES, default=["Egypt"])
cities = col2.multiselect("City / المدينة / المحافظة", GOVERNORATES, default=["Cairo"])
selected_categories = col3.multiselect("Category / المجال", category_names, default=category_names[:1])
roles = col4.multiselect("Business Role / نوع النشاط", ROLES, default=["Manufacturer"])
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

    # Cartesian product of every multi-selected field — an empty field means "no
    # filter" (one run with that value as None). Each combination is a SearchRequest.
    combo_countries = countries or ["Egypt"]
    combo_cities = cities or [None]
    combo_categories = selected_categories or [None]
    combo_roles = roles or [None]
    combos = list(itertools.product(combo_countries, combo_cities, combo_categories, combo_roles))

    if len(combos) > MAX_COMBINATIONS:
        st.error(
            f"التوليفات كتير أوي ({len(combos)}). قلّل الاختيارات (الحد {MAX_COMBINATIONS}). / "
            f"Too many combinations ({len(combos)}) — narrow your selection."
        )
        st.stop()

    st.caption(f"🔁 {len(combos)} توليفة × {len(selected)} مصدر / {len(combos)} combination(s) × {len(selected)} source(s)")
    agg = {"found": 0, "kept": 0, "created": 0, "updated": 0, "dropped": 0}
    drop_reasons: dict[str, int] = {}
    errors: dict[str, str] = {}
    progress = st.progress(0.0)
    with st.spinner("بنجمع الداتا ونفلترها ونقيّمها..."):
        for i, (country, city, category, role) in enumerate(combos, start=1):
            keywords = next((c.get("keywords", []) for c in categories if c["name"] == category), [])
            req = SearchRequest(
                country=country, city=city, category=category, role=role,
                keywords=keywords, max_results=max_results, enrich_websites=enrich,
            )
            stats = run_search(req, selected)
            for key in agg:
                agg[key] += getattr(stats, key)
            for reason, count in stats.drop_reasons.items():
                drop_reasons[reason] = drop_reasons.get(reason, 0) + count
            errors.update(stats.errors)
            progress.progress(i / len(combos))

    st.success(
        f"تم ✅  {len(combos)} توليفة | لقينا {agg['found']} | احتفظنا بـ {agg['kept']} "
        f"(جديد {agg['created']}, محدّث {agg['updated']}) | استبعدنا {agg['dropped']}"
    )
    if drop_reasons:
        st.write("**أسباب الاستبعاد:**", drop_reasons)
    if errors:
        st.error(f"مصادر فشلت: {errors}")
    st.info("افتح صفحة **📋 Leads** من القائمة الجانبية لرؤية النتائج وتحديث الحالات.")
