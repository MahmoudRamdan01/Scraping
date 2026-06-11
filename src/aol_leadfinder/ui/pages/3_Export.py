from __future__ import annotations

import io
import pathlib
import sys

for _p in pathlib.Path(__file__).resolve().parents:
    if _p.name == "src" and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
        break

import streamlit as st  # noqa: E402

from aol_leadfinder.export.excel import leads_to_dataframe, write_styled_workbook  # noqa: E402
from aol_leadfinder.storage.db import mark_pushed_to_sheet, read_all_leads  # noqa: E402
from aol_leadfinder.storage.sheets_sync import (  # noqa: E402
    SheetsNotConfigured,
    append_new_leads,
    is_configured,
    push_dataframe,
)
from aol_leadfinder.ui.common import get_ready_engine  # noqa: E402

st.set_page_config(page_title="Export — Air Ocean Lead Finder", page_icon="📤", layout="wide")
st.title("📤 تصدير / Export")

engine = get_ready_engine()
leads = read_all_leads(engine)
if not leads:
    st.info("لسه مفيش عملاء للتصدير.")
    st.stop()

df = leads_to_dataframe(leads)
st.caption(f"{len(df)} عميل جاهز للتصدير")
st.dataframe(df.head(20), use_container_width=True, hide_index=True)

buffer = io.BytesIO()
write_styled_workbook(df, buffer)
st.download_button(
    "📥 تحميل Excel / Download Excel",
    data=buffer.getvalue(),
    file_name="air_ocean_leads.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)

st.divider()
st.subheader("🔄 مزامنة Google Sheets (Sales_Review)")
if is_configured():
    st.caption("بيضيف **العملاء الجدد بس** في آخر الشيت — مش بيمسح ولا بيلمس أي صف أو عمود موجود.")
    if st.button("➕ ضيف الجديد للشيت / Append new leads", type="primary"):
        try:
            result = append_new_leads(leads)
            if result.appended:
                mark_pushed_to_sheet(engine, [lead.id for lead in result.leads])
            st.success(
                f"تمت الإضافة ✅ {result.appended} عميل جديد "
                f"(تخطّينا {result.skipped} موجودين بالفعل) — {result.url}"
            )
        except SheetsNotConfigured as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error(f"فشلت المزامنة: {exc}")

    with st.expander("⚙️ متقدم: استبدال الشيت بالكامل (بيمسح الشغل اليدوي!)"):
        st.warning("⚠️ ده بيمسح الشيت كله ويعيد كتابته — هيضيّع ملاحظات المبيعات اليدوية. استخدمه بحذر شديد.")
        sheet_name = st.text_input("اسم الشيت / Sheet name", "Air Ocean Leads")
        if st.button("🔄 استبدال كامل / Overwrite all"):
            try:
                url = push_dataframe(df, sheet_name)
                st.success(f"تم الاستبدال ✅ {url}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"فشل: {exc}")
else:
    st.warning(
        "Google Sheets مش متظبط. لتفعيله: اعمل service-account JSON مجاني من Google Cloud، حط محتواه في "
        "`GOOGLE_SHEETS_CRED_JSON` (أو مساره في `GOOGLE_SHEETS_CRED`) و`GOOGLE_SHEET_ID`، وشارك الشيت مع "
        "إيميل الـ service account كـ Editor."
    )
