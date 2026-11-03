# FEATURE_CHECKLIST.md — قائمة تتبع الميزات

> آخر تحديث: 2026-11-03 — **Phase 1 (Foundation) مستقرة**. المرحلة التالية: Phase 2 (Authentication).
>
> **الحالات:** `NOT_STARTED` · `IN_PROGRESS` · `BLOCKED` · `IMPLEMENTED` · `TESTED` · `COMPLETE` — و`N/A` عندما لا ينطبق البُعد على الميزة.
> **COMPLETE** فقط عندما تكون كل الأبعاد المنطبقة `TESTED` والتوثيق مكتملاً.
> الأعمدة: BE = Backend · FE = Frontend · DB = Database · Perm = Permissions · Tests · Docs.
> المراجع: `PRD.md` (المتطلب) · `BUSINESS_RULES.md` (القواعد).

## Phase 0 — Planning

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| P0-01 | وثائق التخطيط | PROJECT_MASTER_PROMPT, PRD, ARCHITECTURE, ERD, BUSINESS_RULES, FEATURE_CHECKLIST | N/A | N/A | N/A | N/A | N/A | COMPLETE | COMPLETE | اعتُمدت 2026-11-03. Q2 (الاستضافة) قبل Phase 9 |

## Phase 1 — Foundation (F-OPS / F-UX / F-RT) — ✅ مستقرة (2026-11-03)

> **IMPLEMENTED** = كُتب وتحقق منه جزئياً. **TESTED** = اجتاز اختبارات آلية أو تشغيلاً فعلياً. التفاصيل في `IMPLEMENTATION_LOG.md`.

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| F-OPS-01 | Docker Compose | dev + prod: postgres, pgbouncer, redis, migrate, api, realtime, worker, beat, web, nginx | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | N/A | IMPLEMENTED | TESTED | IMPLEMENTED | الملفان صالحان (`docker compose config`)، ومكوّنات كل حاوية مختبرة منفصلة. **لم تُبنَ الصور هنا** لأن Docker Hub محجوب في بيئة العمل؛ يُتحقق على جهازك أو في CI |
| F-OPS-02 | Health & Logging | `/health/live`، `/health/ready` (DB, cache, broker, scheduler, channel layer)، JSON logs، request_id، حجب البيانات الحساسة | TESTED | N/A | N/A | TESTED | TESTED | TESTED | COMPLETE | request_id ينتقل من nginx إلى Django إلى Celery |
| F-OPS-03 | CI | ruff, import-linter, migrations, schema, deploy check, pytest, eslint, tsc, vitest, build, docker build | IMPLEMENTED | IMPLEMENTED | N/A | N/A | TESTED | TESTED | IMPLEMENTED | كل خطوة شُغّلت محلياً ونجحت؛ لم يُشغَّل على GitHub بعد (لا يوجد remote) |
| F-OPS-06 | إعدادات البيئة | settings مقسمة (base/dev/test/prod)، `.env.example`، prod يرفض الإعدادات غير الآمنة | TESTED | TESTED | N/A | N/A | TESTED | TESTED | COMPLETE | `check --deploy` بلا تحذيرات |
| F-OPS-07 | Nginx أصل واحد + PgBouncer + Redis ×3 | توجيه `/`, `/api`, `/ws`؛ TLS؛ rate limits؛ transaction pooling؛ عناوين Redis منفصلة | TESTED | N/A | TESTED | N/A | TESTED | TESTED | TESTED | مختبر بـ nginx 1.24 وPgBouncer 1.22 محلياً؛ الصور تستخدم nginx 1.28 وPgBouncer من Alpine 3.22 |
| F-OPS-08 | الحدود المعمارية | import-linter: الدومين لا يعتمد على realtime/channels | TESTED | N/A | N/A | N/A | TESTED | TESTED | COMPLETE | |
| F-OPS-09 | Migrations | نظام migrations + فحص CI؛ نموذج المستخدم المخصص قبل أي migration | TESTED | N/A | TESTED | N/A | TESTED | TESTED | COMPLETE | migrations تتصل بـ Postgres مباشرة لا عبر PgBouncer |
| F-RT-01 | بنية ASGI + Channels | عملية `realtime` مستقلة، Redis Channel Layer، `/ws/system/` (ping/pong + server_time)، رفض Origin الخارجي، إغلاق 1012 عند إعادة النشر | TESTED | N/A | N/A | TESTED | TESTED | TESTED | TESTED | مصادقة الجلسة على WS تكتمل مع Phase 2 (F-AUTH-08) |
| F-RT-02 | EventBus وفصل الطبقات | `publish_on_commit` + `ChannelsEventBus` + registry للربط | TESTED | N/A | N/A | N/A | TESTED | TESTED | TESTED | أُنجز مبكراً لأنه أساس؛ ربط أحداث المزاد في Phase 6 |
| F-RT-05 | عميل WebSocket | Backoff + Jitter، Heartbeat، كشف الاتصال الميت، ساعة الخادم، أكواد الإغلاق النهائية | N/A | TESTED | N/A | N/A | TESTED | TESTED | IN_PROGRESS | الأساس جاهز؛ كشف فجوات `seq` وإعادة المزامنة خاصة بالمزاد (Phase 6) |
| F-UX-01 | Design Tokens والخطوط | `tokens.css` + Tailwind `@theme` + IBM Plex Sans Arabic (ذاتي الاستضافة) | N/A | IMPLEMENTED | N/A | N/A | IMPLEMENTED | TESTED | IMPLEMENTED | مراجعة بصرية/تباين في Phase 8 |
| F-UX-02 | RTL شامل | `dir=rtl`، خصائص منطقية، قاعدة ESLint تمنع الاتجاهات الفيزيائية | N/A | TESTED | N/A | N/A | TESTED | TESTED | TESTED | |
| F-UX-03 | التخطيط والمكونات الأساسية | Header, Footer, Container, Button، 404 معرّبة | N/A | IMPLEMENTED | N/A | N/A | IMPLEMENTED | TESTED | IMPLEMENTED | تُستكمل المكونات مع الصفحات |
| F-UX-06 | i18n | next-intl، روابط عربية بلا بادئة، `messages/ar.json` | N/A | TESTED | N/A | N/A | TESTED | TESTED | TESTED | |
| F-AUTH-00 | نموذج المستخدم المخصص | User برقم هاتف E.164، بريد فريد غير حساس لحالة الأحرف، بلا كلمة مرور للعملاء | TESTED | N/A | TESTED | N/A | TESTED | TESTED | TESTED | أُنشئ مبكراً: لا يمكن تبديل AUTH_USER_MODEL بعد أول migration |

## Phase 2 — Authentication (F-AUTH)

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| F-AUTH-01 | طلب OTP | رقم E.164، رسالة موحدة، Throttle، إرسال عبر WhatsApp خلف `OtpSender` | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-901a؛ الإنتاج يحتاج بيانات خدمة WhatsApp |
| F-AUTH-02 | التحقق من OTP | 5 دقائق، 5 محاولات، hash، إنشاء الحساب | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-901..905 |
| F-AUTH-03 | الجلسة والخروج و`me` | Session cookie + CSRF | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-906 |
| F-AUTH-04 | الملف الشخصي | تعديل الاسم والبريد | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-AUTH-05 | الأدوار وإدارة المستخدمين | Groups + صلاحيات مخصصة + واجهة Super Admin | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-AUTH-06 | MFA للموظفين | TOTP عبر django-otp | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BLOCKED | Q10 |
| F-AUTH-07 | إدارة الجلسات | UserSession، الأجهزة النشطة، الخروج من الأجهزة الأخرى، إبطال إداري، انتهاء العميل/الموظف | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-908..910 |
| F-AUTH-08 | مصادقة WebSocket | جلسة Cookie + Origin validation + إغلاق عند الإبطال | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |

## Phase 3 — Catalog (F-CAT)

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| F-CAT-01 | التصنيفات والمواد والتقنيات والوسوم | CRUD إداري + Seed أولي، تعطيل لا حذف | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-106/107 |
| F-CAT-02 | إدارة الفنانين | عام/داخلي، حالة، صورة، مميز | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-CAT-03 | إدارة الأعمال | كل الحقول، نشر/إخفاء/أرشيف | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-101..105 |
| F-CAT-04 | صور الأعمال | رفع متعدد، ترتيب، رئيسية، نسخ مصغرة، Object Storage | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-104/108 |
| F-CAT-05 | استعراض الأعمال | شبكة، ترتيب، Pagination | NOT_STARTED | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-CAT-06 | تفاصيل العمل | Gallery، Lightbox، أزرار حسب الحالة | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-CAT-07 | صفحة الفنان | نبذة، أعمال متاحة ومؤرشفة | NOT_STARTED | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-CAT-08 | الأرشيف العام | مباع/منتهٍ/مؤرشف، غير قابل للشراء | NOT_STARTED | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-802/803 |

## Phase 4 — Listings, Search, Favorites

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| F-LST-01 | Listing بسعر ثابت | إنشاء/تعديل، عرض نشط واحد لكل عمل، اعتماد التسعير من Super Admin | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-201/202/212 |
| F-LST-02 | أنواع الكمية والمخزون | UNIQUE/LIMITED/UNLIMITED + قيود CHECK + أقفال | NOT_STARTED | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-203..207 |
| F-LST-03 | جدولة العرض وحالاته | starts_at/ends_at، SOLD_OUT مشتق | NOT_STARTED | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-208/209 |
| F-LST-04 | عمولة وعربون العرض | override + الافتراضي العام | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-402/701, Q12 |
| F-CAT-09 | البحث والفلاتر | تطبيع عربي + pg_trgm + فلاتر §21 | NOT_STARTED | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-FAV-01 | المفضلة | إضافة/حذف/عرض، فريدة، منع IDOR | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |

## Phase 5 — Cart & Orders (F-CART / F-ORD)

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| F-CART-01 | عربة التسوق | إضافة/تعديل/حذف، سعر ثابت فقط، لا مزادات، لا حجز | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-321..324, 328 |
| F-CART-02 | Checkout | طلب متعدد العناصر، كل-شيء-أو-لا-شيء، PRICE_CHANGED، Idempotency | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-325..327 |
| F-ORD-01 | إنشاء الطلب | قفل المخزون لكل العناصر، Snapshot، رقم الطلب، مصدر CART/AUCTION | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-301..306, 310/311 |
| F-ORD-02 | سياسة العربون وإقرارها | عرض السياسة المُصدَرة قبل الحجز | NOT_STARTED | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-313 |
| F-ORD-03 | صفحة الطلب للعميل | العدّاد، العربون، WhatsApp Deep Link | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-312, Q14 |
| F-ORD-04 | انتهاء 24 ساعة | للعربون فقط؛ Celery Beat + فحص كسول، تحرير مخزون كل العناصر | NOT_STARTED | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-307/308 |
| F-ORD-05 | إلغاء العميل قبل العربون | من حسابه | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | Q9 |
| F-ORD-06 | إدارة الطلبات | بحث، فلترة، تفاصيل، سجل الحالات، ملاحظات | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-ORD-07 | الدفعات اليدوية | عربون، دفعات، استرداد؛ سجلات غير قابلة للتعديل | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-401..408 |
| F-ORD-08 | انتقالات الحالة والإلغاء | آلة الحالات + OrderStatusHistory | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BUSINESS_RULES §3.1 |
| F-ORD-09 | التسليم | طريقة، جهة، حالة، تاريخ، ملاحظات | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-801 |
| F-ORD-10 | إزالة عنصر من طلب | قبل تأكيد العربون، إعادة حساب الإجمالي والعربون | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-303/409 |

## Phase 6 — Auctions & Realtime (F-AUC / F-RT)

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| F-AUC-01 | تقديم طلب مزاد | نموذج + صور اختيارية + متابعة الحالة | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-601..604 |
| F-AUC-02 | مراجعة طلبات المزاد | حالات، ملاحظات، نسبة المنصة المتفق عليها (إلزامية قبل الموافقة)، قرار | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-605/606/606a |
| F-AUC-03 | إدارة المزادات | إنشاء، جدولة، تعديل قبل البداية، إلغاء | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-501..504 |
| F-AUC-04 | التحولات الزمنية | SCHEDULED→LIVE→ENDED بوقت الخادم | NOT_STARTED | N/A | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-505 |
| F-AUC-05 | المزايدة | HTTP + Idempotency، قفل صف، ساعة Postgres، تمديد، version | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-505..510, Q8 |
| F-AUC-06 | صفحات المزادات العامة | قادمة/نشطة/منتهية + صفحة حية لحظية | NOT_STARTED | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | تعتمد F-RT-03/05 |
| F-AUC-07 | الفائز ومهلة الساعة | Order للفائز بعربون ≥ 50%، AWARDED بعد تأكيده | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-410, 511..515 |
| F-AUC-08 | سياسة عدم الدفع | المزايد التالي / إلغاء الإرساء | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-514 |
| F-AUC-09 | سجل مزايدات العميل | في حساب العميل | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-RT-03 | قناة المزاد العامة | snapshot عند الاتصال، أحداث بـ seq، server_time، أسماء مستعارة | NOT_STARTED | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-507b/c |
| F-RT-04 | قناة المستخدم الخاصة | outbid، فوز، session.revoked | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-RT-05b | إعادة مزامنة المزاد | كشف فجوات `seq`، لقطة REST، دمج الأحداث | N/A | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | يبني على F-RT-05 |
| F-RT-06 | التوسع والتحمّل | عدة نسخ realtime، اختبار تحمّل | NOT_STARTED | N/A | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | |

## Phase 7 — Admin Operations

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| F-ADM-01 | هيكل لوحة الإدارة | تنقل حسب الصلاحية | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | يُبنى تدريجياً من Phase 2 |
| F-ADM-02 | Dashboard | مؤشرات §9.1 | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-ADM-03 | AuditLog | تسجيل + عرض للـ Super Admin | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | الخدمة تُستخدم من Phase 2 |
| F-SET-01 | اتفاقيات الفنانين | نسبة العمولة، اتفاقية نشطة واحدة | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-SET-02 | حساب العمولة | ترتيب الحسم + Snapshot | NOT_STARTED | N/A | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-701..703؛ المنطق يُبنى في Phase 5 |
| F-SET-03 | التسويات | إنشاء عند CONFIRMED + تسجيل الدفع؛ المستفيد فنان أو مالك | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | BR-704..706 |
| F-CMS-01 | الصفحات الثابتة | من نحن، شروط، خصوصية، سياسة العربون (بإصدارات) | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | سياسة العربون مطلوبة في Phase 5 |
| F-CMS-02 | FAQ | CRUD + عرض | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-CMS-03 | البنرات والمختارات | بنرات، أعمال وفنانون مميزون | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-CMS-04 | الصفحة الرئيسية | Hero، مختارات، مزادات، تصنيفات، حديث | NOT_STARTED | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-CMS-05 | إعدادات الموقع | العمولة/العربون الافتراضي، WhatsApp | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-NTF-01 | الإشعارات الداخلية | قائمة الإشعارات للعميل | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-NTF-02 | SMS/Email | Adapter قابل للتبديل، أحداث §26 | NOT_STARTED | N/A | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-UX-04 | الموسيقى | تشغيل/إيقاف بلا autoplay | N/A | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | BLOCKED | Q13: ملف مرخص |

## Phase 8 — QA

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| QA-01 | الأمن | مراجعة §24، فحص الاعتماديات، IDOR | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| QA-02 | الأداء | Query counts، Lighthouse، الصور | NOT_STARTED | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| QA-03 | RTL + Accessibility + Mobile | axe، لوحة المفاتيح، أحجام الشاشات | N/A | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | F-UX-05 |
| QA-04 | E2E السيناريوهات A–D | Playwright | N/A | NOT_STARTED | N/A | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | |
| F-OPS-04 | Backup/Restore | سكربتات + اختبار استعادة | NOT_STARTED | N/A | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | NOT_STARTED | |

## Phase 9 — Deployment

| ID | الميزة | الوصف | BE | FE | DB | Perm | Tests | Docs | Overall | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| F-OPS-05 | النشر | Staging/Prod، Nginx، SSL، Monitoring | NOT_STARTED | NOT_STARTED | NOT_STARTED | N/A | NOT_STARTED | NOT_STARTED | BLOCKED | Q2: الاستضافة |
| DOC-01 | التوثيق الكامل | README، API، Setup، Admin، OTP، Deployment، Backup، Testing | NOT_STARTED | NOT_STARTED | N/A | N/A | N/A | NOT_STARTED | NOT_STARTED | §30 |

---

## خارج النطاق (لن يُنفَّذ)
- ❌ نظام التحقق من الأصالة (BR-004) — لا نماذج، لا جداول، لا API، لا واجهات.
- ❌ بوابة دفع، تحويلات آلية، تكامل شحن، حساب فنان.
- ❌ عربون مشاركة في المزادات (F-AUC-10 أُلغي — BR-516).
- ❌ إدخال أعمال المزاد في عربة التسوق (BR-322).
