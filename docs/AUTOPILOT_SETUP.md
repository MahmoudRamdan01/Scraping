# تشغيل الأوتوبايلوت — إعداد لمرة واحدة (٥ دقايق)

الأوتوبايلوت بيشتغل لوحده كل يوم على GitHub Actions ويضيف الـ leads الجديدة في آخر
شيت **Sales_Review** من غير ما يلمس أي صف أو عمود بيملاه فريق المبيعات يدويًا.
عشان يقدر يكتب في الشيت محتاج ٣ حاجات بتتعمل **مرة واحدة بس** من حساباتك إنت
(مفيش حد غيرك يقدر يعملها):

> ⚠️ **أمان:** ملف الـ JSON اللي هتنزّله هو مفتاح سري. ماتبعتوش في شات/إيميل
> وماترفعوش في الريبو — مكانه الوحيد **GitHub Secrets** (الخطوة B).

---

## A) إنشاء Service Account + مفتاح JSON (≈ ٣ دقايق — مجاني)

1. **اعمل مشروع** (لو مفيش): افتح
   <https://console.cloud.google.com/projectcreate>
   — اسم المشروع أي حاجة، مثلًا `aol-leadfinder` → **Create**.

2. **فعّل الـ APIs** (مرتين Enable):
   - Google Sheets API: <https://console.cloud.google.com/apis/library/sheets.googleapis.com>
   - Google Drive API: <https://console.cloud.google.com/apis/library/drive.googleapis.com>

3. **اعمل Service Account**:
   <https://console.cloud.google.com/iam-admin/serviceaccounts>
   → **Create service account** → الاسم مثلًا `aol-autopilot` → **Create and continue**
   → سيب الـ Roles فاضية (**مش محتاجين أي role** — الصلاحية هتيجي من مشاركة الشيت
   نفسه في الخطوة C) → **Done**.

4. **نزّل مفتاح JSON**: افتح الـ service account اللي لسه عاملُه → تبويب **Keys**
   → **Add key → Create new key → JSON → Create** — هيتنزّل ملف `.json` على جهازك.

5. **خد الإيميل** بتاع الـ service account (شكله:
   `aol-autopilot@aol-leadfinder.iam.gserviceaccount.com`) — هتحتاجه في الخطوة C.

---

## B) إضافة الـ Secrets في GitHub (≈ دقيقة)

افتح صفحة إضافة secret مباشرة:
<https://github.com/MahmoudRamdan01/Scraping/settings/secrets/actions/new>

وضيف **اتنين**:

| Name | Value |
|---|---|
| `GOOGLE_SHEETS_CRED_JSON` | **محتوى** ملف الـ JSON كله — افتح الملف بأي محرر نصوص، Ctrl+A ثم Ctrl+C، والصقه في الخانة |
| `GOOGLE_SHEET_ID` | `19EXCx1hAGUwZtbL9zTqHOxtaQM_qQaot51ojMuGvIlA` |

---

## C) مشاركة الشيت مع الـ Service Account (≈ نص دقيقة)

1. افتح شيت **Sales_Review**:
   <https://docs.google.com/spreadsheets/d/19EXCx1hAGUwZtbL9zTqHOxtaQM_qQaot51ojMuGvIlA/edit>
2. زرار **Share** (مشاركة) → الصق إيميل الـ service account من الخطوة A-5
   → اختار **Editor** → **Send**.
   (لو طلع تنبيه إن الإيميل خارجي أو مش هيوصله إشعار — كمّل عادي، ده طبيعي.)

---

## D) التجربة الأولى

من GitHub: تبويب **Actions** → workflow اسمه **Autopilot** → زرار **Run workflow**.
- علّم ✅ على `dry_run` لو عايز تجرب من غير كتابة في الشيت.
- شغّله عادي (من غير dry_run) → هتلاقي في آخر اللوج سطر زي:
  `autopilot: segments=12 found=… kept=… appended=… skipped=…`
  والصفوف الجديدة ظهرت في آخر الشيت بـ `Status=new` و`Added Date`.

بعد كده هيشتغل **لوحده يوميًا الساعة 06:00 UTC** (≈ 08:00 بتوقيت مصر) — كل يوم
شريحة مختلفة من المجالات (rotation بيغطي كل الأولويات خلال أسبوعين).

---

## حل المشاكل الشائعة

| الخطأ في اللوج | السبب والحل |
|---|---|
| `PERMISSION_DENIED` / `The caller does not have permission` | الشيت مش متشارك مع إيميل الـ service account كـ **Editor** → اعمل الخطوة C |
| `SERVICE_DISABLED` / `Google Sheets API has not been used` | الـ API مش متفعّل في المشروع → اعمل الخطوة A-2 |
| `SpreadsheetNotFound` / `Requested entity was not found` | قيمة `GOOGLE_SHEET_ID` غلط → اتأكد إنها `19EXCx1hAGUwZtbL9zTqHOxtaQM_qQaot51ojMuGvIlA` |
| `sheet not configured` في اللوج | secret ناقص أو اسمه متكتب غلط → راجع الخطوة B بالحرف |
| Google Maps بيرجّع 0 نتائج في الـ CI | طبيعي أحيانًا (حظر data-center IPs) — باقي المصادر بتكمّل عادي |

> **ملاحظة:** نفس الإعداد بيشغّل زرار «➕ ضيف الجديد للشيت» في صفحة Export محليًا —
> حط في ملف `.env` إما `GOOGLE_SHEETS_CRED` (مسار ملف الـ JSON) أو
> `GOOGLE_SHEETS_CRED_JSON` (محتواه) + `GOOGLE_SHEET_ID`.
