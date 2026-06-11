"""Best-effort decision-maker extraction (name / role / email) from page text.

Air Ocean's sales team wants to reach the person who owns shipping decisions —
the Export Manager, the Logistics Manager, or the Owner/CEO. This finds the
highest-priority such role mentioned on a site and pairs it with a personal-
looking email. Any field may be None; the role + a non-generic email is already
useful even without a name.
"""
from __future__ import annotations

import re
from typing import Optional

# Priority order: export > logistics > owner/CEO. Stored label is English; the
# keyword lists are Arabic + English so both site languages are covered.
_ROLE_BUCKETS: list[tuple[str, tuple[str, ...]]] = [
    ("Export Manager", (
        "export manager", "export director", "head of export", "export sales manager",
        "مدير التصدير", "مدير الصادرات", "مدير قطاع التصدير", "مسؤول التصدير",
    )),
    ("Logistics Manager", (
        "logistics manager", "supply chain manager", "logistics director", "head of logistics",
        "shipping manager", "مدير اللوجستيات", "مدير الخدمات اللوجستية", "مدير سلسلة الإمداد", "مدير الشحن",
    )),
    ("Owner / CEO", (
        "chief executive", "ceo", "managing director", "general manager", "owner",
        "founder", "co-founder", "chairman", "الرئيس التنفيذي", "المدير العام",
        "المالك", "صاحب الشركة", "مؤسس", "رئيس مجلس الإدارة",
    )),
]

_NAME = (
    r"(?:[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){1,2}"
    r"|[؀-ۿ]{2,}(?:\s+[؀-ۿ]{2,}){1,3})"
)
_GENERIC_LOCALS = {
    "info", "sales", "contact", "support", "admin", "office", "mail",
    "hello", "customercare", "care", "service", "enquiry", "inquiries",
}


def best_personal_email(emails) -> Optional[str]:
    """First email whose local-part looks like a person, not a role inbox."""
    for e in emails or []:
        local = str(e).split("@")[0].lower()
        if local and local not in _GENERIC_LOCALS:
            return e
    return None


def _name_near(text: str, kw: str) -> Optional[str]:
    m = re.search(rf"({_NAME})\s*[,\-–—|:]\s*{re.escape(kw)}", text, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(rf"{re.escape(kw)}\s*[:\-–—|]\s*({_NAME})", text, re.I)
    if m:
        return m.group(1).strip()
    return None


def extract_contacts(text: Optional[str], emails=None) -> dict:
    """{name, role, email} for the highest-priority role found, or {} if none."""
    t = text or ""
    low = t.lower()
    for label, kws in _ROLE_BUCKETS:
        for kw in kws:
            if kw in low:
                return {"name": _name_near(t, kw), "role": label, "email": best_personal_email(emails)}
    return {}
