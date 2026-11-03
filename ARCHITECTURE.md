# ARCHITECTURE.md — المعمارية (v2)

> المرجع: `PROJECT_MASTER_PROMPT.md` §4. الإصدار v2 يعتمد مراجعة الاستدامة طويلة الأمد (2026-11-03):
> المصادقة بالجلسات على نطاق واحد، مزادات لحظية عبر ASGI + Channels + WebSockets من البداية، عربة تسوق للأعمال ذات السعر الثابت.
> القرارات المعلَّمة **[ADR-xx]** موثقة في §13.

---

## 1. المبادئ الحاكمة

1. **PostgreSQL هو مصدر الحقيقة الوحيد** للحالة التجارية (مخزون، طلبات، مزايدات، دفعات). Redis للتسريع والتوزيع فقط — فقدانه لا يفقد بيانات تجارية.
2. **منطق الأعمال مستقل عن وسيلة النقل**: القواعد في طبقة Domain/Services لا تعرف HTTP ولا WebSocket ولا Celery.
3. **خدمات بلا حالة (Stateless)**: كل عملية تشغيل (API, Realtime, Worker, Next.js) قابلة للنسخ أفقياً دون Sticky Sessions.
4. **Modular Monolith**: قاعدة كود Django واحدة، تُشغَّل كأنواع عمليات مختلفة (Process Types) تتوسع كل منها مستقلة. لا Microservices ولا Kubernetes في MVP، لكن الصور Twelve-Factor فلا يلزم تغيير الكود عند الانتقال لاحقاً.
5. **وقت قاعدة البيانات هو الساعة المرجعية** لكل قرار زمني حساس (قبول مزايدة، انتهاء حجز).
6. **لا تعقيد غير مبرر**: كل مكوّن إضافي له سبب موثق في §13.

---

## 2. الطوبولوجيا

```
                         ┌─────────────────────────────── Nginx / Load Balancer (TLS, HSTS, rate limit) ───────────────────────────────┐
                         │                                                                                                         │
 Browser ── HTTPS/WSS ──►│  https://damascene-art.example/           → Next.js (SSR/RSC)           ×N                              │
                         │  https://damascene-art.example/api/v1/*   → api  (Django WSGI, Gunicorn) ×N                              │
                         │  wss://damascene-art.example/ws/*         → realtime (Django ASGI, Channels, Uvicorn) ×N                │
                         └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 Browser ── HTTPS ──► https://media.damascene-art.example  → CDN → Object Storage (S3-compatible)  (نطاق بلا Cookies)

 Next.js (server) ──► http://api:8000 (شبكة داخلية، يمرّر Cookie المستخدم للقراءة فقط)

 api / realtime / worker ──► PgBouncer ──► PostgreSQL 16 (primary)      [+ read replica لاحقاً]
 api / realtime / worker ──► Redis: cache+sessions | celery broker | channel layer   (عناوين منفصلة)
 worker ×N (Celery queues: critical, default, media, notifications)   +   beat ×1 (singleton)
```

| Process Type | التقنية | الدور | التوسع |
|---|---|---|---|
| `web` | Next.js `next start` | الواجهة العامة والحساب ولوحة الإدارة | أفقي |
| `api` | Django + DRF على Gunicorn (WSGI, gthread) | REST API — كل عمليات الكتابة بما فيها المزايدة | أفقي |
| `realtime` | Django ASGI + Channels على Gunicorn/Uvicorn workers | WebSockets للبث اللحظي فقط | أفقي |
| `worker` | Celery | المهام الخلفية بطوابير منفصلة | أفقي |
| `beat` | Celery Beat + django-celery-beat | الجدولة | **نسخة واحدة فقط** |
| `pgbouncer` | PgBouncer (transaction pooling) | تجميع اتصالات Postgres | — |

لماذا `api` و`realtime` منفصلان رغم أنهما نفس الكود؟ **[ADR-08]** DRF والـ ORM متزامنان (sync)؛ تشغيلهما تحت WSGI أبسط وأكفأ. الـ WebSockets تحتاج ASGI واتصالات طويلة. الفصل يسمح بتوسيع كل منهما حسب حمله، ويمنع أن تؤثر آلاف الاتصالات المفتوحة على زمن استجابة الـ API. `config/asgi.py` يخدم HTTP أيضاً عند الحاجة (للتطوير أو كخطة بديلة).

---

## 3. النطاقات وأثرها على المصادقة **[ADR-01]**

| الخيار | الوصف | أثره على المصادقة | القرار |
|---|---|---|---|
| **A. أصل واحد (Same-origin)** | `example/` للواجهة، `/api/` و`/ws/` يوجّههما Nginx | Cookie مضيف فقط (host-only) ببادئة `__Host-`، لا CORS، `SameSite=Lax` يعمل طبيعياً، CSRF بسيط، WebSocket يستلم نفس Cookie تلقائياً | ✅ **معتمد** |
| B. نطاقات فرعية (`www.` + `api.`) | نفس الموقع (same-site) بأصلين | يتطلب `Domain=.example` (Cookie يصل لكل النطاقات الفرعية ← سطح هجوم أكبر)، CORS مع `credentials`، Preflight لكل طلب، `CSRF_TRUSTED_ORIGINS` | ❌ |
| C. نطاقات مختلفة | `example-art.com` + `example-api.com` | Cookies طرف ثالث تحجبها Safari/Firefox، والجلسات لا تعمل موثوقاً | ❌ مرفوض |

- الصور على `media.` (أو نطاق CDN) **بلا Cookies** — أسرع ولا يكشف الجلسة.
- التوسع الأفقي لا يتأثر بالخيار A: الـ Load Balancer يوجّه حسب المسار (`/api`, `/ws`, `/`) إلى مجموعات خوادم مختلفة.

---

## 4. المصادقة وإدارة الجلسات **[ADR-06]**

### 4.1 التدفق
1. `POST /api/v1/auth/otp/request` ← رسالة موحدة دائماً (BR-905)، throttle لكل رقم وIP. الرمز يُرسل عبر **WhatsApp** من خلال `OtpSender` (§4.5) في طابور `critical`.
2. `POST /api/v1/auth/otp/verify` ← عند النجاح: `login()` مع `cycle_key()` (منع Session Fixation)، إنشاء سجل `UserSession`، إصدار Cookie.
3. الطلبات اللاحقة: Cookie الجلسة + ترويسة `X-CSRFToken` لكل طلب غير آمن (POST/PUT/PATCH/DELETE).
4. `POST /api/v1/auth/logout` ← `flush()` + إبطال `UserSession` + إغلاق WebSockets الخاصة بالمستخدم.

### 4.2 الإعدادات
| الإعداد | القيمة |
|---|---|
| `SESSION_ENGINE` | `cached_db` — Postgres دائم + Redis للسرعة (فقدان Redis لا يُخرج المستخدمين) |
| `SESSION_COOKIE_NAME` | `__Host-sid` — `Secure; HttpOnly; SameSite=Lax; Path=/` بلا Domain |
| `CSRF_COOKIE_NAME` | `__Host-csrf` — `Secure; SameSite=Lax` (مقروء من JS لإرساله في الترويسة) |
| `SECURE_SSL_REDIRECT`, HSTS | مفعّل، HSTS سنتان + preload |
| `SECURE_PROXY_SSL_HEADER` | يُوثق بها من Nginx فقط |
| انتهاء جلسة العميل | 30 يوماً كحد أقصى مع تجديد منزلق عند تجاوز نصف المدة |
| انتهاء جلسة الموظف | 12 ساعة مطلقة + 30 دقيقة خمول، وMFA عند كل دخول |

### 4.3 إدارة الجلسات
- جدول `UserSession`: hash مفتاح الجلسة، الجهاز (User-Agent مختصر)، IP، `created_at`, `last_seen_at` (يُحدَّث كل 5 دقائق كحد أقصى)، `revoked_at`.
- العميل: صفحة "الأجهزة النشطة" + "تسجيل الخروج من الأجهزة الأخرى".
- Super Admin: إبطال كل جلسات مستخدم؛ تعطيل الحساب يبطلها تلقائياً.
- عند الإبطال: رسالة `session.revoked` إلى مجموعة `user.{id}` في Channels فتُغلق اتصالات WebSocket المفتوحة.

### 4.4 Next.js مع الجلسات
- **القراءة على الخادم (RSC)**: Next.js يستدعي `http://api:8000` داخلياً ويمرّر ترويسة `Cookie` الواردة كما هي. لا يخزّن ولا يقرأ قيمة الجلسة.
- **عمليات الكتابة من المتصفح مباشرة** إلى `/api/v1/...` (same-origin) مع `X-CSRFToken`. **لا تُستخدم Next Server Actions أو Route Handlers كوكيل لعمليات الكتابة** حتى لا يتشتت مسار حماية CSRF.
- `middleware.ts` في Next.js يعيد التوجيه لتحسين التجربة فقط؛ الحماية الفعلية في DRF.

### 4.5 إرسال رمز التحقق (WhatsApp) **[ADR-16]**
```
accounts/otp/
  senders/base.py        # OtpSender: send(phone, code, locale) → SendResult(provider_message_id, status)
  senders/console.py     # التطوير والاختبار: يطبع في السجل المحلي فقط (معطّل في prod)
  senders/whatsapp.py    # مزود WhatsApp المعتمد (يُضبط بالـ ENV: URL، مفتاح API، اسم القالب)
  senders/sms.py         # لاحقاً عند الحاجة
```
- الاختيار بالإعداد `OTP_SENDER=whatsapp`، والأسرار في ENV فقط.
- الإرسال في مهمة Celery مع إعادة محاولة محدودة. الرمز لا يظهر في Logs أبداً؛ يُمرَّر للمهمة مشفّراً (Fernet، صلاحية 5 دقائق) ولا يُحفظ نصاً في أي مكان، وفي قاعدة البيانات يُخزَّن كـ HMAC فقط.
- تحديثات حالة التسليم (Webhook من المزود إن توفرت) تُحدّث `delivery_status`، مع التحقق من توقيع الـ Webhook.
- مخاطر القناة: المستخدم بلا WhatsApp، أو قيود المزود على الأرقام السورية، أو تعليق الحساب التجاري. التخفيف: Adapter ثانٍ (SMS أو مزود WhatsApp بديل) يُضاف بالإعداد دون تغيير الكود.

### 4.6 التوسع المستقبلي (دون إعادة هندسة)
- تطبيق جوال أصلي لا يناسبه Cookie. خدمة `verify_otp()` تُرجع مستخدماً موثقاً بمعزل عن وسيلة حمل الهوية، فيمكن لاحقاً **إضافة** DRF Authentication Class للتوكنات (Access قصير + Refresh مخزّن ومُبطَل من جدول `UserSession` نفسه) دون تغيير أي منطق أعمال. **[ADR-09]**

---

## 5. المزادات اللحظية **[ADR-05 v2]**

### 5.1 فصل الطبقات

```
auctions/
  domain.py      # قواعد خالصة: validate_bid(state, amount, user, now) → BidDecision ; compute_extension(...)
                 # لا ORM، لا Channels — تُختبر كدوال صرفة
  services.py    # place_bid(), start_auction(), close_auction(), declare_winner(), expire_winner_payment()
                 # transaction.atomic + SELECT … FOR UPDATE + حفظ + رفع Domain Events عبر on_commit
  events.py      # dataclasses: BidPlaced, AuctionExtended, AuctionStarted, AuctionEnded, WinnerPending, AuctionAwarded, AuctionCancelled, UserOutbid
core/events.py   # EventBus: publish(event) ← واجهة؛ التنفيذ يُحقن بالإعدادات
realtime/        # التطبيق الوحيد الذي يعرف Channels
  publisher.py   # ChannelsPublisher: يحوّل Domain Events إلى رسائل group_send
  consumers.py   # AuctionConsumer, UserConsumer (AsyncJsonWebsocketConsumer)
  routing.py
```

- `auctions` لا يستورد `channels` أبداً (يُفرض باختبار import-linter).
- في الاختبارات يُستخدم `InMemoryEventBus` للتحقق من الأحداث دون WebSocket.

### 5.2 المزايدة: HTTP للكتابة، WebSocket للبث **[ADR-10]**
- المزايدة تُرسل عبر `POST /api/v1/auctions/{id}/bids` وليس عبر WebSocket، للأسباب التالية:
  - استجابة نهائية مؤكدة لكل مزايدة (قُبلت/رُفضت + السبب + الحالة الجديدة).
  - حماية CSRF وThrottling وAudit موحدة مع باقي الـ API.
  - انقطاع WebSocket لا يؤثر على القدرة على المزايدة ولا على نتيجتها.
- **Idempotency**: كل مزايدة تحمل ترويسة `Idempotency-Key` (UUID من العميل). قيد فريد `(user, idempotency_key)`. إعادة الإرسال بعد انقطاع الشبكة تُرجع **نفس النتيجة** ولا تُنشئ مزايدة ثانية.

### 5.3 معاملة المزايدة (PostgreSQL مرجع نهائي)
```
BEGIN;
  SELECT … FROM auction WHERE id = :id FOR UPDATE;          -- تسلسل المزايدات على المزاد الواحد
  now := clock_timestamp();                                  -- ساعة قاعدة البيانات
  decision := domain.validate_bid(state, amount, user, now)  -- status LIVE, starts_at ≤ now < ends_at, الحد الأدنى…
  INSERT bid …; UPDATE previous highest → OUTBID;
  UPDATE auction SET current_price, highest_bid_id, bid_count, ends_at (تمديد), version = version + 1;
COMMIT;
on_commit → event_bus.publish(BidPlaced(seq=version, …), UserOutbid(…), AuctionExtended?(…))
```
- قرار القبول يعتمد على `ends_at` المخزّن ووقت قاعدة البيانات، **لا على حقل status** ولا على ساعة الخادم أو المتصفح. أي مزايدة بعد `ends_at` مرفوضة حتى لو لم تُشغَّل مهمة الإغلاق بعد.
- `version` يزداد بمقدار 1 مع كل تغيير في حالة المزاد داخل نفس المعاملة المقفلة ← ترتيب الأحداث مضمون ومتسلسل بلا فجوات.

### 5.4 بروتوكول WebSocket

**الاتصال**: `wss://…/ws/auctions/{public_id}/` (عام، قراءة فقط) و`wss://…/ws/me/` (خاص بالمستخدم المسجّل: تجاوز مزايدتك، فوزك، إبطال الجلسة).
- المصادقة: نفس Cookie الجلسة عبر `AuthMiddlewareStack`؛ التحقق من `Origin` عبر `AllowedHostsOriginValidator` (حماية من Cross-Site WebSocket Hijacking).

**شكل الرسالة الموحد:**
```json
{ "type": "bid.placed", "auction": "a1b2…", "seq": 128, "server_time": "2026-11-03T10:15:02.120Z", "data": { … } }
```

| type | المحتوى |
|---|---|
| `auction.snapshot` | الحالة الكاملة (يُرسل عند الاتصال) |
| `bid.placed` | المبلغ، الاسم المستعار للمزايد (مثل "مزايد 3")، السعر الحالي، عدد المزايدات |
| `auction.extended` | `ends_at` الجديد |
| `auction.started` / `auction.ended` / `auction.winner_pending` / `auction.awarded` / `auction.cancelled` | الحالة |
| `user.outbid` (خاص) | تم تجاوز مزايدتك |
| `session.revoked` (خاص) | إغلاق الاتصال |
| `ping` / `pong` | Heartbeat كل 25 ثانية |

- هوية المزايد لا تُكشف للعامة: اسم مستعار ثابت لكل مزاد (`Bid.bidder_alias`).

### 5.5 الانقطاع وإعادة الاتصال وإعادة المزامنة
1. العميل يحتفظ بـ `last_seq`.
2. عند (إعادة) الاتصال: يستقبل `auction.snapshot` (يحوي `seq`) ويستبدل حالته المحلية بالكامل، ثم يطبّق الأحداث التي `seq > snapshot.seq` فقط.
3. **كشف الفجوات**: إذا وصل حدث بـ `seq ≠ last_seq + 1` ← يطلب الحالة عبر `GET /api/v1/auctions/{id}/state` ويُعيد البناء.
4. إعادة المحاولة: Exponential Backoff (1s ← 30s) مع Jitter لتجنب موجة إعادة اتصال جماعية بعد إعادة نشر الخوادم.
5. عند عودة التبويب للواجهة (`visibilitychange`) أو عودة الشبكة (`online`) ← إعادة مزامنة فورية.
6. أثناء الانقطاع: الواجهة تعرض "جارٍ إعادة الاتصال" بوضوح. زر المزايدة يبقى يعمل عبر HTTP، والخادم يرفض أي مبلغ لم يعد صالحاً ويُرجع السعر الحالي.
7. **لا يوجد Polling دوري كآلية أساسية**؛ الـ REST يُستخدم فقط للقطة الأولية وسد الفجوات.

لماذا لا نحتاج Outbox؟ إذا سقطت عملية بين COMMIT ونشر الحدث، يفوت العملاء حدثاً واحداً، ثم يكتشفون الفجوة من `seq` التالي أو عند إعادة الاتصال ويعيدون المزامنة من Postgres. المزايدة نفسها محفوظة ومؤكدة للمزايد عبر استجابة HTTP. **[ADR-11]**

### 5.6 الوقت
- `server_time` في كل رسالة وكل استجابة REST. العميل يحسب الفرق بين ساعته وساعة الخادم ويعرض العد التنازلي بناءً عليه، ولا يتخذ أي قرار.
- عند وصول العد إلى الصفر تعرض الواجهة "جارٍ إغلاق المزاد" حتى يصل `auction.ended`.
- كل الخوادم مزامنة بـ NTP، وقرارات القبول بساعة Postgres.

### 5.7 بدء المزادات وإغلاقها
- مهمة `auction_tick` على طابور `critical` كل 5 ثوانٍ: تختار المزادات المستحقة للبدء أو الإغلاق بـ `FOR UPDATE SKIP LOCKED` (آمنة مع عدة Workers)، وتستدعي `start_auction` / `close_auction` (Idempotent).
- دقة البث ≤ 5 ثوانٍ؛ أما **العدالة** فلا تعتمد على هذه المهمة لأن القبول محكوم بـ `ends_at` (§5.3).
- إغلاق المزاد يحدد الفائز وينشئ Order (`source=AUCTION`، عربون ≥ 50%، مهلة ساعة) في نفس المعاملة.
- `expire_winner_payments` كل دقيقة + فحص كسول ← تطبيق `non_payment_policy`.

### 5.8 التوسع الأفقي
- `realtime` بلا حالة: أي نسخة تخدم أي اتصال، والبث عبر Redis Channel Layer (`channels_redis`) يصل لكل النسخ.
- لا Sticky Sessions (اتصال WebSocket ثابت على نسخة واحدة طوال عمره).
- المستهلكون لا يستعلمون من قاعدة البيانات لكل رسالة؛ الحدث يحمل كل ما يلزم. الاستعلام الوحيد هو اللقطة عند الاتصال (استعلام واحد مخزّن مؤقتاً لثانية واحدة لامتصاص موجات الاتصال).
- عنق الزجاجة المتوقع هو قفل صف المزاد الواحد، أي تسلسل المزايدات على المزاد نفسه. هذا مقصود لضمان الصحة، ويحتمل مئات المزايدات في الثانية للمزاد الواحد. المزادات المختلفة لا تتنافس على الأقفال نفسها.
- عند النمو: Redis مخصص للـ Channel Layer ثم Redis Cluster بتغيير الإعداد فقط.
- Graceful shutdown: عند إعادة النشر تُغلق الاتصالات برمز 1012، فيعيد العميل الاتصال بـ Backoff.

---

## 6. عربة التسوق والطلبات **[ADR-12]**

- `Cart` واحدة لكل مستخدم مسجّل، مخزّنة في Postgres (تعمل عبر الأجهزة). الإضافة تتطلب تسجيل الدخول.
- العربة **لا تحجز مخزوناً**؛ الحجز يحدث عند Checkout فقط.
- العربة لأعمال `FIXED_PRICE` فقط. **المزادات خارج العربة**؛ كل فوز بمزاد ينشئ طلباً مستقلاً بعنصر واحد.
- Checkout = معاملة واحدة **كل شيء أو لا شيء**: قفل كل الـ Listings المعنية مرتبةً بالـ id (منع Deadlocks) ← التحقق من الكل ← إنشاء Order واحد بعدة OrderItems ← حجز المخزون ← تفريغ العناصر المحوّلة من العربة.
- عند تغيّر السعر منذ الإضافة يرجع الخطأ `PRICE_CHANGED` مع القيم الجديدة، ويؤكد العميل مجدداً.
- عند عدم توفر عنصر: يرجع `ITEMS_UNAVAILABLE` مع قائمة العناصر، ولا يُحجز شيء.

---

## 7. Backend

### 7.1 الإصدارات
Python 3.12 · Django 5.2 LTS · DRF 3.15+ · Channels 4 + channels_redis · Uvicorn · PostgreSQL 16 · PgBouncer · Redis 7 · Celery 5 + django-celery-beat · drf-spectacular · django-storages · Pillow · django-otp · pytest + pytest-django + pytest-asyncio + factory_boy · import-linter.

> **الإصدارات المثبّتة فعلياً (Phase 1):** Django 5.2.18 LTS · DRF 3.18.3 · Channels 4.3.2 · channels-redis 4.3.0 · Celery 5.6.3 · django-celery-beat 2.9.0 · drf-spectacular 0.30.0 · psycopg 3.3.7 · Gunicorn 26.2 · Uvicorn 0.54 · PgBouncer (Alpine 3.22). القائمة الكاملة في `backend/requirements/`.
> Pillow وdjango-otp تُضاف في المراحل التي تستخدمها (3 و2).

### 7.2 التطبيقات

| App | المسؤولية |
|---|---|
| `core` | الإعدادات المشتركة، EventBus، أخطاء API موحدة، Pagination، Money/Time utils، تطبيع العربية، Idempotency، Health، SiteSetting |
| `accounts` | User، OTP، UserSession، الأدوار، MFA |
| `catalog` | Category، Material، Technique، Tag |
| `artists` | Artist، ArtistAgreement |
| `artworks` | Artwork، ArtworkImage، الصور، البحث |
| `listings` | Listing، InventoryService |
| `favorites` | Favorite |
| `cart` | Cart، CartItem، CheckoutService |
| `orders` | Order، OrderItem، PaymentRecord، Delivery، آلة الحالات، الانتهاء |
| `auctions` | Auction، Bid، AuctionRequest — منطق خالص مستقل عن النقل |
| `realtime` | Channels consumers + publisher (طبقة نقل فقط) |
| `settlements` | Settlement، حساب العمولات |
| `cms` | Page، FaqItem، Banner، FeaturedItem |
| `notifications` | Notification + Adapters (SMS/Email/In-app) |
| `audit` | AuditLog |

### 7.3 الطبقات داخل كل تطبيق
```
app/
  models.py      # البيانات والقيود
  domain.py      # (عند الحاجة) قواعد خالصة بلا ORM
  services.py    # عمليات الكتابة + transaction.atomic + الأقفال + الأحداث
  selectors.py   # الاستعلامات (select_related/prefetch_related)
  serializers.py
  api/public.py  api/admin.py
  permissions.py  tasks.py  admin.py  tests/
```
- قواعد الاعتماد (يفرضها import-linter في CI): `api → services → domain`؛ `realtime → core.events` فقط؛ لا شيء يستورد `realtime` عدا التوصيل في الإعدادات.
- ترتيب الأقفال الثابت: `Listing (بالـ id تصاعدياً) → Order → Auction`.

### 7.4 API
- `/api/v1/` عام و`/api/v1/admin/` للإدارة. OpenAPI عبر drf-spectacular ← Types للواجهة.
- **المعرّفات العامة**: `slug` للأعمال والفنانين، `order_number` للطلبات، `public_id` (UUID) للمزادات وطلبات المزاد. لا أرقام تسلسلية في الروابط (يمنع التعداد، ويسمح بنقل البيانات لاحقاً). **[ADR-13]**
- أخطاء موحدة: `{ "error": { "code", "message", "details" } }` برسائل عربية.
- Idempotency-Key مدعوم لكل POST مالي أو حساس (Checkout، المزايدة، تسجيل الدفعات).

### 7.5 Celery
| Queue | المهام |
|---|---|
| `critical` | `auction_tick` (5s)، `expire_winner_payments` (1m)، `expire_pending_orders` (1m) |
| `default` | التسويات، الإحصاءات |
| `media` | معالجة الصور |
| `notifications` | SMS/Email |

- `beat` نسخة واحدة فقط، والجدول في قاعدة البيانات (django-celery-beat). كل المهام Idempotent وتستدعي Services، والانتهاء يُفحص أيضاً بشكل كسول (BR-308).

### 7.6 قاعدة البيانات
- PgBouncer بوضع transaction pooling منذ البداية: `CONN_MAX_AGE=0`، `DISABLE_SERVER_SIDE_CURSORS=True`. الأقفال تعمل لأنها داخل المعاملة.
- `selectors` تقبل `using=` حتى يمكن لاحقاً توجيه قراءات الكتالوج العامة إلى Read Replica. قراءات المزاد والمخزون تبقى على الـ Primary دائماً.
- النسخ الاحتياطي: WAL archiving (wal-g أو pgBackRest) للاستعادة إلى نقطة زمنية (PITR) + `pg_dump` يومي مشفّر، مع اختبار استعادة دوري.

### 7.7 Redis
ثلاثة عناوين منفصلة بالإعدادات: `REDIS_CACHE_URL` (cache + sessions cache + throttling)، `CELERY_BROKER_URL`، `CHANNEL_LAYER_URL`. تكون في البداية قواعد منطقية على نفس الخادم، وفصلها لاحقاً تغيير إعداد فقط.

---

## 8. Frontend

### 8.1 الإصدارات
Next.js 15 (App Router) · React 19 · TypeScript strict · Tailwind CSS 4 · TanStack Query 5 · React Hook Form + Zod · Radix UI · next-intl · openapi-typescript.

> **تحديث Phase 1 (يحتاج موافقتك — انظر `IMPLEMENTATION_LOG.md`):** اعتُمد **Next.js 16.4** بدل 15 لأنه الإصدار المستقر الحالي، ونسخة 15 أقرب إلى نهاية الدعم. الأثر الوحيد هو تسمية `middleware.ts` إلى `proxy.ts`، دون أي تغيير معماري.
> الإصدارات المثبّتة: Next 16.4.4 · React 19.3.1 · TypeScript 5.9.3 (لأن openapi-typescript لا يدعم 6.x بعد) · Tailwind 4.3.4 · next-intl 4.14.9 · TanStack Query 5.105 · Zod 4.6 · Vitest 5.1 · ESLint 9.39 (لأن إضافات eslint-config-next لا تدعم ESLint 10 بعد).
> React Hook Form وRadix UI تُضاف مع أول نموذج أو مكوّن تفاعلي (Phase 2).

### 8.2 الهيكل
```
frontend/
  app/
    [locale]/                  # next-intl بـ localePrefix: 'as-needed' — العربية بلا بادئة في الرابط
      (public)/ (auth)/ (account)/ admin/
  components/ ui/ layout/ art/
  features/
    artworks/ artists/ listings/ cart/ orders/ auctions/ favorites/ auction-requests/ admin/
  lib/
    api/        # server client (يمرّر Cookie) + browser client (CSRF)
    realtime/   # AuctionSocket: reconnect, backoff, heartbeat, seq/gap detection, resync
    auth/ validation/ formatters/
  messages/ar.json            # كل نصوص الواجهة (جاهزة للإنجليزية لاحقاً)
  styles/tokens.css
  types/api.d.ts              # مولّد من OpenAPI
```

### 8.3 مبادئ
- **i18n من البداية** **[ADR-14]**: النصوص في `messages/ar.json` عبر next-intl. إضافة الإنجليزية لاحقاً = ملف ترجمة + LTR، دون تغيير روابط العربية. محتوى قاعدة البيانات عربي في MVP.
- **RTL**: خصائص منطقية فقط (`ms-*`, `ps-*`, `start-*`)، وقاعدة ESLint تمنع `ml-/mr-/left-/right-`.
- **Design Tokens** في `tokens.css` فقط.
- المزاد الحي: `useAuctionLive(id)` يجمع اللقطة (TanStack Query) والـ WebSocket في Store واحد مرتب بالـ `seq`.
- الأرقام: لاتينية للأسعار (ADR-04، يحتاج تأكيد).

---

## 9. التخزين والصور
- django-storages؛ قاعدة البيانات تخزن **مفاتيح** الملفات لا الروابط، فتغيير CDN أو المزود لا يتطلب ترحيل بيانات.
- Bucket عام للأعمال (عبر CDN) وBucket خاص لصور طلبات المزاد (روابط موقّعة قصيرة العمر).
- التحقق من المحتوى، إزالة EXIF/GPS، وتوليد نسخ WebP: 400 / 1000 / 2000.

## 10. الإشعارات
`Notification` تُكتب في Postgres داخل معاملة الحدث (on_commit)، ثم تُرسل عبر طابور `notifications` بـ Adapter (`EmailProvider`، ولاحقاً WhatsApp/SMS). رموز OTP مسار منفصل (§4.5). تغيير المزود = تنفيذ Adapter جديد + إعداد.

## 11. الأمن
same-origin + `__Host-` cookies + CSRF · HSTS/CSP/X-Frame-Options/Referrer-Policy · Origin validation للـ WebSocket · Throttling (OTP، Checkout، المزايدة) في Redis · Idempotency · منع IDOR في selectors · MFA للموظفين · إدارة الجلسات وإبطالها · AuditLog غير قابل للتعديل · فحص الملفات · detect-secrets + pip-audit + npm audit في CI.

## 12. المراقبة والتشغيل
- Logs بصيغة JSON مع `request_id` يمر من Nginx إلى Django وCelery، وحجب الحقول الحساسة.
- Metrics: `django-prometheus` (api/realtime)، ومن مقاييس realtime: عدد الاتصالات، معدل الرسائل، زمن البث.
- Health: `/api/v1/health/live|ready` (DB, Redis ×3, Storage)، وفحص اتصال للـ realtime.
- تتبع الأخطاء: Sentry أو بديل ذاتي الاستضافة (GlitchTip) حسب التوفر.
- `docker-compose.yml` (dev) و`docker-compose.prod.yml` (prod) بنفس الصور ونفس Process Types.

## 13. سجل القرارات المعمارية

| ADR | القرار | البديل المرفوض | السبب |
|---|---|---|---|
| 01 | أصل واحد عبر Nginx (`/`, `/api`, `/ws`) | نطاقات فرعية / نطاقات مختلفة | Cookies أصل واحد، بلا CORS، WebSocket بنفس الجلسة |
| 02 | آلة حالات صريحة في Services | django-fsm | وضوح، بلا اعتماد إضافي |
| 03 | Types مولّدة من OpenAPI | Types يدوية | منع الانحراف بين العقد والواجهة |
| 04 | أرقام لاتينية للأسعار | هندية | وضوح — **يحتاج تأكيد** |
| 05v2 | Channels + WebSockets + Redis من البداية | Polling | قرارك؛ لحظية دون إعادة هندسة |
| 06 | Django Sessions (`cached_db`) + UserSession | JWT | إبطال فوري، لا تخزين في المتصفح |
| 07 | لوحة إدارة في Next.js + Django Admin داخلياً | Django Admin فقط | متطلب §9 |
| 08 | فصل `api` (WSGI) عن `realtime` (ASGI) | ASGI واحد لكل شيء | توسع مستقل، عزل الأحمال |
| 09 | Auth قابل لإضافة Token لاحقاً | — | تطبيق جوال مستقبلي دون إعادة هندسة |
| 10 | المزايدة عبر HTTP + Idempotency، والبث عبر WS | المزايدة عبر WS | نتيجة مؤكدة، CSRF، لا فقدان عند الانقطاع |
| 11 | `seq` + كشف الفجوات بدل Outbox | Transactional Outbox | Postgres مرجع والعملاء يعيدون المزامنة؛ تعقيد أقل |
| 12 | عربة في Postgres بلا حجز؛ الحجز عند Checkout | حجز عند الإضافة | منع حجب المخزون |
| 13 | معرّفات عامة (slug/order_number/UUID) | IDs تسلسلية | منع التعداد وسهولة الترحيل |
| 14 | next-intl منذ البداية | نصوص مضمّنة | الإنجليزية لاحقاً دون إعادة كتابة |
| 15 | PgBouncer + WAL/PITR منذ البداية | pg_dump فقط | جاهزية إنتاج وتوسع الاتصالات |
| 16 | OTP عبر WhatsApp خلف واجهة `OtpSender` | ربط مباشر بمزود SMS | قرارك؛ تبديل القناة أو المزود بالإعداد فقط |

---

## 14. مراجعة مخاطر إعادة الهندسة

| # | القرار / المنطقة | لماذا قد يسبب إعادة هندسة | الحل المعتمد |
|---|---|---|---|
| 1 | طوبولوجيا النطاقات | تغيير النطاقات لاحقاً يكسر Cookies وCORS وWebSocket | أصل واحد من البداية (ADR-01) |
| 2 | آلية التحديث اللحظي | Polling ثم WS = إعادة كتابة الواجهة والبنية | Channels من البداية مع فصل الطبقات (§5) |
| 3 | ربط منطق المزاد بالـ WebSocket | يصعب الاختبار وتغيير النقل | Domain/Services + EventBus (§5.1) |
| 4 | طلب بعنصر واحد | إضافة العربة لاحقاً تغيّر Orders والمخزون والعربون | عربة + Order متعدد العناصر الآن (§6) |
| 5 | تطبيق جوال مستقبلي | الجلسات لا تناسبه | Auth قابل للتوسيع (ADR-09) |
| 6 | تعدد اللغات | نصوص مضمّنة في الكود | next-intl الآن (ADR-14) |
| 7 | المعرّفات في الروابط | IDs تسلسلية مكشوفة | معرّفات عامة (ADR-13) |
| 8 | العملة | إضافة عملة لاحقاً تمس كل المبالغ | حقل `currency` ثابت `USD` على Order/Payment/Settlement بلا منطق تحويل |
| 9 | اتصالات Postgres | توسع الخوادم يستنزف الاتصالات | PgBouncer الآن، ومنع server-side cursors |
| 10 | Redis واحد لكل شيء | الفصل لاحقاً يتطلب تغيير الكود | ثلاثة عناوين منفصلة بالإعدادات |
| 11 | Celery Beat متعدد النسخ | تكرار المهام | نسخة واحدة + مهام Idempotent + SKIP LOCKED |
| 12 | البحث | pg_trgm قد لا يكفي عند ملايين السجلات | `ArtworkSearch` selector كواجهة؛ الاستبدال بـ Meilisearch/OpenSearch لاحقاً دون تغيير الـ API |
| 13 | نمو AuditLog / Bid | جداول ضخمة | فهارس زمنية؛ Partitioning شهري متاح لاحقاً دون تغيير الكود |
| 14 | تخزين روابط الملفات | تغيير CDN يتطلب ترحيلاً | تخزين المفاتيح فقط |
| 15 | المستفيد من التسوية | افتراض الفنان دائماً | `payee_type` = ARTIST / OWNER منذ البداية |

**ما لم نضفه عمداً (تجنباً للتعقيد):** Kubernetes، Microservices، Event Sourcing، Kafka، Transactional Outbox، CQRS منفصل، GraphQL، Read Replica من اليوم الأول.

## 15. هيكل المستودع
```
/
  PROJECT_MASTER_PROMPT.md  PRD.md  ARCHITECTURE.md  ERD.md  BUSINESS_RULES.md  FEATURE_CHECKLIST.md  README.md
  backend/
    config/ settings/{base,dev,prod,test}.py  urls.py  wsgi.py  asgi.py  celery.py  routing.py
    apps/ core accounts catalog artists artworks listings favorites cart orders auctions realtime settlements cms notifications audit
    requirements/  manage.py  pyproject.toml  .importlinter
  frontend/
  infra/ nginx/  docker/  pgbouncer/  scripts/ (backup, restore, seed_demo)
  docs/ api/ deployment.md backup-restore.md testing.md admin-setup.md otp-provider.md realtime.md
  .github/workflows/ci.yml
```
