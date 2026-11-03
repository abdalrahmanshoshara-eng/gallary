# IMPLEMENTATION_LOG.md — سجل التنفيذ

> سجل زمني لما بُني واختُبر وتقرر في كل مرحلة. الأحدث في الأعلى.
> الحالات التفصيلية لكل ميزة في `FEATURE_CHECKLIST.md`.

---

## Phase 2 — Authentication · 2026-11-03 · ✅ مستقرة

### قرارات معتمدة قبل البدء
- **Next.js 16**: مُعتمد.
- **الأرقام**: لاتينية (ADR-04).
- **لا MFA للموظفين**: حسابات الموظفين ينشئها Super Admin فقط (BR-907). أُزيل django-otp وF-AUTH-06 من الخطة.
- **WhatsApp معطّل** حتى الاشتراك بالخدمة (BR-901c).
- **التخزين (ADR-17)**: SeaweedFS في التطوير بدل MinIO، لأن نسخة MinIO المجتمعية صارت مؤرشفة ومصدرية فقط منذ 2025–2026. الإنتاج يستخدم S3 مُداراً إن توفر، وإلا SeaweedFS ذاتي الاستضافة. الكود لا يرتبط بأي مزود (django-storages). يُضاف في Phase 3.

### ما الذي نُفّذ

**Backend**
- `apps/accounts`:
  - `phone.py`: تطبيع إلى E.164 بـ phonenumbers، ويقبل الأرقام العربية و`00` والصيغة المحلية السورية.
  - `models.py`: ‏`OtpChallenge` و`UserSession`، و`User.public_id` بثلاث خطوات آمنة للجداول التي فيها بيانات.
  - `otp/crypto.py`: ‏HMAC مربوط بالرقم مع مقارنة ثابتة الوقت. الرمز يمر إلى Celery مشفّراً بـ Fernet صالحاً 5 دقائق.
  - `otp/senders.py`: ‏`OtpSender` مع `DisabledSender` و`ConsoleSender` (للتطوير فقط، يكتب مباشرة إلى stdout لا إلى السجلات).
  - `tasks.deliver_otp`: على طابور critical مع إعادة محاولة.
  - `services/otp.py`:
    - الطلب: قفل advisory لكل رقم (آمن مع PgBouncer)، مهلة إعادة الإرسال، حد بالساعة لكل رقم ولكل IP، إبطال الرموز السابقة.
    - التحقق: `select_for_update`، المحاولات الخاطئة تُحفظ قبل إظهار الخطأ، إنشاء الحساب عند أول دخول.
  - `services/sessions.py` و`middleware.py`: تتبع الجلسات، والإبطال (فوري عبر cache ومضمون عبر فحص DB كل 5 دقائق)، وسياسة الموظف (12 ساعة / 30 دقيقة خمول)، وتجديد جلسة العميل، وإنهاء الجلسة عند تغيّر الصلاحيات.
  - `services/users.py`: الملف الشخصي، وإنشاء الموظفين وترقيتهم وتعديل أدوارهم وإلغاؤها، والتعطيل والتفعيل، وإنهاء الجلسات إدارياً. الحمايات: لا تعديل للذات، ولا حذف لآخر مدير عام. كل عملية تُسجَّل في AuditLog ضمن المعاملة نفسها.
  - `roles.py`: أربعة أدوار، و`IsSuperAdmin`، وmigration ينشئ المجموعات.
  - API:
    - `/api/v1/auth/{csrf, otp/request, otp/verify, logout, me, sessions, sessions/revoke-others, sessions/<id>}`.
    - `/api/v1/admin/{roles, staff, staff/<id>, users, users/<id>/activate|deactivate|revoke-sessions}`.
  - أمر `bootstrap_super_admin`.
- `apps/audit`: ‏`AuditLog` append-only (الحفظ والحذف ممنوعان على مستوى النموذج، وDjango Admin للقراءة فقط).
- `apps/realtime`:
  - كل WebSocket مسجّل يرتبط بمجموعة `session.<id>`.
  - حدث `SessionRevoked` يُغلق المقابس بـ 4409.
  - `/ws/me/` قناة خاصة تتطلب الدخول.
  - لا يُقبل اتصال بجلسة ملغاة.
- `core/http.client_ip` يثق بعدد البروكسيات المحدد فقط (`NUM_PROXIES`)، و`core/pagination`.
- nginx: حد المصادقة الصارم صار على `/api/v1/auth/otp/` فقط، و`me` و`sessions` تخضع لحد الـ API العام.

**Frontend**
- صفحة `/login`: خطوتان (الرقم ثم الرمز)، عد تنازلي لإعادة الإرسال، رسائل الخادم بالعربية مع عدد المحاولات المتبقية، `autocomplete="one-time-code"`، و`?next=` محمي من open redirect.
- صفحة `/account`: الملف الشخصي، والأجهزة المتصلة مع إنهاء جلسة أو كل الجلسات الأخرى، وتسجيل الخروج.
- `/admin`: لوحة تعرض الأقسام حسب الدور. للمدير العام فقط: `/admin/staff` (إضافة موظف، تعديل الأدوار، إلغاء الصلاحيات) و`/admin/users` (بحث وفلترة وترقيم صفحات، تعطيل مع سبب، تفعيل، إنهاء الجلسات).
- الحراسة على الخادم: الزائر يُحوَّل إلى `/login?next=…`، والعميل يرى 404 في صفحات الإدارة، وDjango يعيد التحقق من كل طلب API.
- الصفحات العامة بقيت static: حالة الدخول في الـ Header تُجلب من المتصفح (`useCurrentUser`)، فلا تصبح كل الصفحات ديناميكية.
- CSRF bootstrap تلقائي قبل أول طلب كتابة. React Hook Form + Zod للتحقق السريع في الواجهة، والخادم هو المرجع.
- مكونات: `Field` و`Alert` و`UserMenu`.

### الاختبارات ونتائجها

| الفحص | النتيجة |
|---|---|
| Backend pytest (PostgreSQL + Redis حقيقيان) | ✅ **137 passed** |
| ruff + format + import-linter + makemigrations --check + schema up-to-date + check --deploy | ✅ |
| prod يرفض `OTP_SENDER=console` | ✅ ImproperlyConfigured |
| Frontend vitest | ✅ **38 passed** (9 ملفات) |
| eslint + typecheck + next build + check:api | ✅ |
| migration `public_id` على بيانات موجودة (رجوع إلى 0001 ثم إدراج صفوف ثم ترقية) | ✅ صفان ← معرّفان فريدان ولا قيم فارغة |
| **E2E حقيقي في Chromium عبر nginx** (Gunicorn + Uvicorn + Celery + Next standalone) | ✅ 9 خطوات — انظر أدناه |

**سيناريو E2E:**
1. زائر يفتح `/admin/staff` فيُحوَّل إلى الدخول مع `next`.
2. المدير يدخل بأرقام عربية، والرمز يصل عبر الـ worker، فيعود إلى `/admin/staff`.
3. إضافة موظفة من الواجهة.
4. عميل جديد على شاشة موبايل يُنشأ حسابه عند أول دخول.
5. حفظ الاسم.
6. العميل على `/admin` يرى 404، وعلى API الإدارة يحصل على 403.
7. العميل يفتح `/ws/me/`.
8. المدير يعطّل العميل، فيصل `session.revoked` ويُغلق المقبس بـ **4409**، وأول طلب API بعدها يعيد 403.
9. خروج المدير، فيعود رابط "تسجيل الدخول" إلى الـ Header.

### مشاكل ظهرت وحُلّت
1. **إعادة توجيه خاطئة بعد الدخول** (اكتشفها اختبار E2E): الـ admin layout كان يحوّل إلى `next=/admin` الثابت، فيضيع المسار الذي طلبه المستخدم، لأن الـ layout لا يعرف المسار الحالي. الحل: كل صفحة تحرس نفسها بمسارها، والـ layout يعرض التنقل فقط.
2. **Celery يحوّل stdout إلى سجلات**، ففلتر الحجب أخفى رمز التطوير (`code=[REDACTED]`). هذا دليل على أن الحماية تعمل، لكنه يعطّل ConsoleSender. الحل: `CELERY_WORKER_REDIRECT_STDOUTS = False`.
3. **أرقام اختبار غير صالحة**: ‏`+963912…` ليس رقماً سورياً صالحاً وفق phonenumbers. استُبدل بأرقام صالحة.
4. **اتصال DB يبقى مفتوحاً من خيط asgiref** في اختبارات WebSocket، فيظهر تحذير عند حذف قاعدة الاختبار. أُضيف fixture يغلقه.
5. **قاعدتان من React Compiler lint** (setState داخل effect): أُعيدت كتابة `useCountdown` بحساب القيمة أثناء العرض، وإعادة ضبط رقم الصفحة صارت في معالجات الأحداث.
6. **phonenumbers**: اعتُمد `phonenumberslite` (بيانات الأرقام دون بيانات المناطق والمشغّلين) لتقليل الحجم.

### ما بقي (بقصد)
- مزود WhatsApp الفعلي: ينتظر اشتراكك. يُضاف كـ `OtpSender` جديد دون تغيير المنطق.
- صلاحيات كل دور على بيانات الكتالوج والطلبات والمزادات: تُضاف مع ميزاتها في المراحل القادمة.
- واجهة عرض AuditLog: Phase 7.

### الخطوة التالية — Phase 3: Catalog
- التصنيفات والمواد والتقنيات والوسوم مع Seed أولي.
- الفنانون والأعمال والصور، مع SeaweedFS في التطوير (ADR-17) ومعالجة الصور.
- الصفحات العامة وإدارة المحتوى، مع صلاحيات `content_staff`.

---

## Phase 1 — Foundation · 2026-11-03 · ✅ مستقرة

### الملخص
هيكل كامل قابل للتشغيل والإنتاج دون أي ميزة تجارية بعد:
- Django مقسّم إلى عمليتين: `api` (WSGI) و`realtime` (ASGI مع Channels).
- Celery مع worker وbeat.
- Next.js بالعربية وRTL.
- nginx على أصل واحد.
- PgBouncer بنمط transaction pooling.
- Redis بثلاثة عناوين منفصلة.
- CI وتوثيق.

### ما الذي نُفّذ

**Backend (`backend/`)**
- `config/settings/{base,dev,test,prod}.py`: كل الإعدادات من متغيرات البيئة. `prod` يرفض العمل بإعدادات غير آمنة: مفتاح سري قصير، Cookies غير Secure، `ALLOWED_HOSTS` أو `CSRF_TRUSTED_ORIGINS` فارغان. الجلسات `cached_db` في Cookie `__Host-sid` مع CSRF. DRF آمن افتراضياً (`IsAuthenticated`)، وكل endpoint عام يُعلن ذلك صراحة.
- `config/asgi.py`: ‏`ProtocolTypeRouter` + `AuthMiddlewareStack` + `AllowedHostsOriginValidator` (حماية من Cross-Site WebSocket Hijacking).
- `config/celery.py`: أربعة طوابير (critical, default, media, notifications)، و`acks_late`، وbeat بجدول في قاعدة البيانات، ونقل `request_id` من الطلب إلى المهمة.
- `config/gunicorn/{api,realtime}.py`: ‏gthread للـ API، وUvicorn workers للـ realtime، مع graceful shutdown.
- `apps/core`:
  - `RequestIdMiddleware`.
  - تسجيل JSON مع حجب الأسرار وإخفاء أرقام الهواتف.
  - غلاف أخطاء موحّد `{"error": {code, message, details, request_id}}` برسائل عربية، يُطبَّق على أخطاء DRF وأخطاء Django و404 لأي مسار `/api/` غير معروف في كل البيئات.
  - `AppError` وأصنافه.
  - `EventBus` مع `publish_on_commit`: لا يُنشر أي حدث إلا بعد نجاح المعاملة، وفشل النقل لا يُفشل العملية.
  - فحوص الجاهزية: قاعدة البيانات، الـ cache، الـ broker، الـ scheduler (يُعتبر degraded فقط ولا يُفشل الجاهزية)، الـ channel layer.
  - مهمة `scheduler_heartbeat`.
- `apps/accounts`: نموذج `User` مخصص برقم هاتف E.164. أُنشئ الآن لأن `AUTH_USER_MODEL` لا يمكن تبديله بعد أول migration. البريد فريد دون حساسية لحالة الأحرف عبر فهرس جزئي، والعملاء بلا كلمة مرور قابلة للاستخدام.
- `apps/realtime`:
  - بروتوكول الرسائل الموحد (`type`, `seq`, `server_time`, `data`) وأكواد الإغلاق.
  - `BaseJsonConsumer`: heartbeat، رفض الرسائل غير الصالحة أو الكبيرة، تمرير رسائل المجموعات.
  - `SystemConsumer` على `/ws/system/` (ping/pong مع وقت الخادم لمزامنة الساعة).
  - `ChannelsEventBus` و`registry` لربط أحداث الدومين برسائل WebSocket.
  - فحص الـ channel layer.
- `.importlinter`: عقدان يمنعان `core` و`accounts` من الاعتماد على `realtime` أو `channels`.
- `openapi/schema.yml`: مولّد ومُتحقق منه (`--validate --fail-on-warn`).

**Frontend (`frontend/`)**
- Next.js 16 (App Router) مع TypeScript strict و`noUncheckedIndexedAccess`.
- Tailwind 4: Design Tokens في `styles/tokens.css` فقط، ومربوطة بـ `@theme`.
- خط IBM Plex Sans Arabic مستضاف ذاتياً عبر `@fontsource`، فلا اعتماد على Google في وقت البناء.
- next-intl بإعداد `localePrefix: 'as-needed'` (روابط عربية بلا بادئة). `proxy.ts` للغة فقط، وليس حداً أمنياً.
- `app/[locale]/`: الـ layout (`lang="ar" dir="rtl"`)، والصفحة الرئيسية بمحتوى تعريفي حقيقي بلا بيانات وهمية ولا روابط ميتة، وصفحة 404 معرّبة لكل المسارات غير المعروفة، و`/healthz` للحاوية.
- `lib/api/`:
  - `client.ts`: same-origin، ترويسة `X-CSRFToken` للطرق غير الآمنة، `Idempotency-Key`.
  - `server.ts`: للقراءة فقط من RSC، ويمرّر Cookie الزائر إلى Django.
  - `errors.ts`: ‏`ApiError` يقرأ الغلاف الموحد بـ Zod.
- `lib/realtime/`:
  - `RealtimeSocket`: إعادة اتصال بـ backoff أسّي مع jitter كامل، وheartbeat، وكشف الاتصال الميت، وعدم إعادة الاتصال بعد أكواد الإغلاق النهائية، و`reconnectNow`، و`onOpen` كنقطة لإعادة المزامنة.
  - `ServerClock`: تقدير فرق الساعة بأسلوب NTP.
- `lib/formatters/`: الدولار بأرقام لاتينية، والتاريخ بتوقيت دمشق، والعد التنازلي.
- `components/`: ‏SiteHeader وSiteFooter وContainer وButton وProviders (TanStack Query، ولا إعادة محاولة لأخطاء 4xx).
- ESLint: قاعدة تمنع أصناف الاتجاه الفيزيائي (`ml-`, `mr-`, `left-`, `text-left`…)، و`no-explicit-any`، و`consistent-type-imports`.
- `types/api.d.ts`: مولّد من مخطط OpenAPI.

**Infrastructure**
- `infra/docker/backend.Dockerfile`: صورة واحدة لكل عمليات الـ backend، بأهداف `dev` و`prod`، ومستخدم غير root، و`tini`، وتشغيل `collectstatic` وقت البناء.
- `infra/docker/frontend.Dockerfile`: هدف `dev` وهدف `prod` بخادم standalone، ومستخدم غير root، وHEALTHCHECK.
- `infra/pgbouncer/`: صورة Alpine مع template وentrypoint يولّدان الإعداد وملف المصادقة من البيئة (SCRAM)، ولا كلمات مرور داخل الصورة.
- `infra/nginx/`:
  - إعدادات مشتركة: upstreams، تمرير request_id، rate limits، سجلات JSON.
  - `snippets/routes.conf`: التوجيه حسب المسار.
  - `dev/default.conf`: HTTP.
  - `prod/default.conf.template`: TLS وHTTP/2 وHSTS وCSP وبقية الترويسات الأمنية.
- `docker-compose.yml` (التطوير) و`docker-compose.prod.yml` (الإنتاج على مضيف واحد):
  - `migrate` يتصل بـ Postgres مباشرة، أما التطبيق فعبر PgBouncer.
  - beat نسخة واحدة فقط.
  - تدوير السجلات وHealthchecks.
- `.github/workflows/ci.yml`: ثلاث مهام (backend, frontend, docker).
- `Makefile`، `.env.example`، `.gitignore`، `.gitattributes` (LF إلزامي حتى على Windows)، `.editorconfig`، `.dockerignore`.

### الاختبارات التي شُغّلت ونتائجها

| الفحص | النتيجة |
|---|---|
| Backend pytest على PostgreSQL 16 حقيقي (`REDIS_INTEGRATION=1`) | ✅ **42 passed** |
| Backend pytest بدون Redis | ✅ 41 passed, 1 skipped (اختبار Redis الحقيقي) |
| Backend pytest **عبر PgBouncer** (transaction pooling) | ✅ 40/40 (قبل إضافة اختبارين لاحقين) — انظر المشكلة 3 |
| `ruff check` + `ruff format --check` | ✅ |
| `lint-imports` | ✅ 2 kept, 0 broken |
| `makemigrations --check` | ✅ No changes detected |
| `check --deploy --fail-level WARNING` بإعدادات prod | ✅ 0 issues |
| `spectacular --validate --fail-on-warn` + تطابق المخطط | ✅ |
| Frontend vitest | ✅ **22 passed** (6 ملفات) |
| `eslint --max-warnings=0` | ✅، والتحقق بملف تجريبي أن قاعدة RTL ترفض `ml-4 text-left` وتقبل `ms-4 text-start` |
| `next typegen && tsc --noEmit` | ✅ |
| `next build` (standalone) | ✅ |
| `npm run check:api` (الأنواع مطابقة للمخطط) | ✅ |
| `docker compose config` (dev وprod) | ✅ صالحان |
| YAML ملف CI | ✅ صالح |

**تشغيل فعلي للعمليات** (Gunicorn وUvicorn وCelery worker وbeat وNext standalone وnginx وPgBouncer، على Postgres وRedis أصليين):
- `/health/ready` أعاد `ready` بكل الفحوص، وأصبح فحص الـ scheduler `ok` بعد أول نبضة من beat عبر طابور `critical`.
- عبر nginx:
  - `/` تعرض Next بـ `<html lang="ar" dir="rtl">`.
  - `/api/` تصل إلى Django، و`/ws/system/` تصل إلى Channels (زمن الذهاب والإياب 1.6ms).
  - `X-Request-ID` يمر من nginx إلى Django إلى Celery ويظهر في سجلات المهام.
  - `/healthz` محجوب (404)، و`/static/` يعمل.
  - rate limit المصادقة يعيد 429 بعد burst بالضبط.
- WebSocket من Origin خارجي ← **403**.
- إيقاف عملية realtime ← العملاء يستلمون كود الإغلاق **1012**، فيعيدون الاتصال.
- إعداد الإنتاج TLS (مُولَّد من الـ template بشهادة self-signed):
  - إعادة توجيه HTTP إلى HTTPS، وHTTP/2.
  - ترويسات HSTS وCSP وX-Frame-Options وPermissions-Policy.
  - `wss://` يعمل.
- محاكاة خطوة `collectstatic` في صورة الإنتاج ببيئة نظيفة دون `.env` ← تولّد manifest سليم.

### المشاكل التي ظهرت وكيف حُلّت

1. **صور Docker Hub محجوبة في بيئة عملي** (403 من الـ proxy). لم أستطع بناء الصور أو تشغيل `docker compose up` هنا. البديل الذي اتبعته: اختبرت كل مكوّن بالأداة نفسها مثبّتة محلياً (Postgres 16، Redis، PgBouncer، nginx، Gunicorn، Uvicorn، Celery، Next standalone)، وتحققت من صلاحية ملفات Compose، وأضفت بناء الصور إلى CI. **المطلوب: تشغيل `docker compose up -d --build` على جهازك** (أوامر README).
2. **psycopg 3 والـ prepared statements**: ‏psycopg 3 يحضّر الاستعلام على الخادم بعد 5 تنفيذات، وهذا لا يعمل مع transaction pooling. الحل: `prepare_threshold = None` في الإعدادات، وتحققت بـ 20 استعلاماً متكرراً عبر PgBouncer.
3. **الاختبارات عبر PgBouncer**: كلها تنجح، لكن حذف قاعدة الاختبار في النهاية يفشل لأن PgBouncer يحتفظ باتصالات مفتوحة إليها. هذا خاص ببيئة الاختبار فقط. **القرار:** الاختبارات والـ migrations تتصل بـ Postgres مباشرة (كما في CI وخدمة `migrate`)، والتطبيق عبر PgBouncer.
4. **Celery كان يتجاوز إعدادات السجلات**، فلم تكن بصيغة JSON. الحل: `CELERY_WORKER_HIJACK_ROOT_LOGGER = False`.
5. **إخفاء أرقام الهواتف كان واسعاً جداً** وأفسد UUIDs والطوابع الزمنية في السجلات. ضُيّق النمط إلى أرقام مستقلة من 9 إلى 15 خانة، وأُضيفت اختبارات تمنع تكرار الخطأ.
6. **صفحة 404 لـ Django بصيغة HTML في وضع DEBUG** لمسارات `/api/` غير الموجودة. أُضيف مسار catch-all يعيد غلاف JSON في كل البيئات، فلا يختلف سلوك التطوير عن الإنتاج.
7. **`channels.testing` يتطلب daphne**: أُضيف إلى `requirements/dev.txt` فقط.
8. **openapi-typescript لا يدعم TypeScript 6** ← TypeScript 5.9.3. **إضافات eslint-config-next لا تدعم ESLint 10** ← ESLint 9.39.5، وهي أداة تطوير فقط.
9. **`__Host-` cookies تتطلب HTTPS**، فبيئة التطوير (HTTP) تستخدم `sid`/`csrftoken`، والإنتاج يبقى على `__Host-sid`/`__Host-csrf`. الأسماء تُضبط بالبيئة، وحاوية الواجهة تستلم الاسم المناسب.
10. **خادم Next.js standalone** يجب أن يستمع على `HOSTNAME=0.0.0.0` داخل الحاوية، وقد ضُبط في الـ Dockerfile.

### قرارات تحتاج موافقتك
- **Next.js 16.4 بدل 15** (مذكور في `ARCHITECTURE.md` §8.1): الإصدار 16 هو المستقر الحالي، والفرق الوحيد تسمية `middleware.ts` ← `proxy.ts`. يمكن الرجوع إلى 15 إن رغبتِ.
- **تخزين الملفات في التطوير (MinIO)**: لم أضف حاوية تخزين في هذه المرحلة لأن أول استخدام لها في Phase 3. التوثيق ينص على MinIO، لكن طريقة توزيع نسختها المجانية تغيّرت مؤخراً. سأتحقق من الخيار الأنسب (MinIO بإصدار مثبّت، أو بديل متوافق مع S3) قبل Phase 3 وأعرضه عليك.
- **ADR-04 (أرقام لاتينية للأسعار)** ما زال بانتظار التأكيد. المنسّق الحالي يستخدم أرقاماً لاتينية، وتغييره سطر واحد.

### ما لم يكتمل في هذه المرحلة (بقصد)
- مصادقة WebSocket بالجلسة تعمل تقنياً (`AuthMiddlewareStack`)، لكن لا يوجد تسجيل دخول قبل Phase 2.
- لم يُشغَّل CI على GitHub بعد، لأنه لا يوجد remote. كل خطوة فيه شُغّلت محلياً.
- النسخ الاحتياطي (WAL/PITR) والمراقبة يُنفّذان في Phase 8/9 كما في الخطة.

### الخطوة التالية — Phase 2: Authentication
- OTP عبر WhatsApp خلف واجهة `OtpSender` (ConsoleSender في التطوير).
- `UserSession` وإدارة الجلسات.
- الأدوار (Groups) والصلاحيات.
- MFA للموظفين (بانتظار تأكيد Q10).
- مصادقة WebSocket وإغلاقه عند إبطال الجلسة.
- صفحة الدخول في الواجهة.

يحتاج تشغيل Phase 2 في الإنتاج اسم خدمة WhatsApp ووثائق الـ API الخاصة بها، أما التطوير فيعمل دونها.
