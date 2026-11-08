# gallary

# منصة الفن الدمشقية — Damascene Art Platform

A managed art marketplace with a digital archive and live auctions. The interface is in Arabic and right-to-left (RTL), and prices are in USD.

| Document | Content |
|---|---|
| [`PROJECT_MASTER_PROMPT.md`](PROJECT_MASTER_PROMPT.md) | Original requirements (source of truth) |
| [`PRD.md`](PRD.md) | Product requirements, scope, phases, open questions |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Architecture and decision records (ADR-01…16) |
| [`ERD.md`](ERD.md) | Data model |
| [`BUSINESS_RULES.md`](BUSINESS_RULES.md) | Business rules `BR-xxx` |
| [`FEATURE_CHECKLIST.md`](FEATURE_CHECKLIST.md) | Feature status |
| [`IMPLEMENTATION_LOG.md`](IMPLEMENTATION_LOG.md) | What was built, tested and decided, phase by phase |

**Current status:** Phase 2 (Authentication) is complete: phone + OTP login, tracked sessions, staff roles managed by the Super Admin, session-bound WebSockets. Catalogue features start in Phase 3 — see `FEATURE_CHECKLIST.md`.

---

## Architecture at a glance

```
http://localhost:8080  ──►  nginx ──┬── /          → web       (Next.js 16, TypeScript)
                                    ├── /api/      → api       (Django 5.2 + DRF, Gunicorn WSGI)
                                    └── /ws/       → realtime  (Django Channels, Uvicorn ASGI)
api · realtime · worker · beat ──► pgbouncer ──► PostgreSQL 16
                              └──► Redis 7 (cache · Celery broker · channel layer)
```

The whole site runs on one origin, so the session cookie, CSRF and WebSocket authentication need no CORS (ADR-01). The `api` and `realtime` processes are separate process types built from the same backend image, and each scales on its own (ADR-08). Domain code publishes events and never imports the WebSocket layer; this is enforced by `import-linter` (ADR-05v2).

## Repository layout

```
backend/           Django project
  config/          settings (base/dev/test/prod), urls, wsgi, asgi, celery, gunicorn configs
  apps/core/       request ids, JSON logging + redaction, error envelope, events, health checks
  apps/accounts/   custom phone-based User model (OTP login arrives in Phase 2)
  apps/realtime/   Channels consumers, event→WebSocket publisher, protocol
  openapi/         generated OpenAPI schema (committed; CI checks it is current)
frontend/          Next.js App Router
  app/[locale]/    pages (Arabic, unprefixed URLs via next-intl)
  components/      layout + UI primitives
  lib/api/         browser/server API clients, error envelope
  lib/realtime/    resilient WebSocket client (backoff, heartbeat, server clock)
  styles/tokens.css  design tokens — the only place brand colours live
  types/api.d.ts   generated from backend/openapi/schema.yml
infra/             Dockerfiles, nginx (dev + TLS prod), PgBouncer image
.github/workflows/ci.yml
```

---

## Run locally (Docker — recommended)

Requirements: Docker Desktop (or Docker Engine) with Compose v2.

```bash
cp .env.example .env          # local-only values; never commit .env
docker compose up -d --build  # first build takes a few minutes
docker compose ps             # wait until api / realtime are "healthy"
```

Open **http://localhost:8080**. Useful checks:

```bash
curl http://localhost:8080/api/v1/health/ready      # database, cache, broker, scheduler, channel layer
docker compose logs -f api realtime worker beat     # follow logs
docker compose exec api python manage.py createsuperuser   # internal admin at /internal-admin/
docker compose down                                 # stop (data volumes are kept)
```

The scheduler check reports `degraded` until Celery beat completes its first one-minute heartbeat. That is expected right after startup.

### Sign-in and accounts

Everyone signs in with **phone number + password** at http://localhost:8080/login.

- **Super Admin**: created automatically by the `migrate` service (`ensure_super_admin`) from `DEFAULT_SUPER_ADMIN_PHONE` / `DEFAULT_SUPER_ADMIN_PASSWORD`. Development defaults: `0943959774` / `admin123456`. Change the password from **حسابي** after the first sign-in; restarts never reset it. **Production refuses the development password**, so set a strong one in the server's `.env`.
- **Staff**: created by the Super Admin from **لوحة الإدارة ← الموظفون** with an initial password. There is no MFA (BR-907).
- **Customers**: register themselves at `/register` (name, phone, email, governorate, city, address, password).
- **Password rules**: at least 8 characters, a letter and a digit, not all digits, not a common password, and not too similar to the user's name, phone or email.
- **Forgotten password**: the Super Admin sets a new one from **المستخدمون** or **الموظفون**, which also ends all of that user's sessions. Self-service reset needs WhatsApp (below).
- Failed sign-ins are locked for 15 minutes after 5 attempts per phone (30 per IP).

Phone numbers are **not verified yet**. The WhatsApp code service (`OTP_SENDER`, `services/otp.verify_otp`) is kept for confirming numbers once the subscription is active (BR-901c). Until then `phone_verified` stays `false`.

`make help` lists shortcuts for the same commands (`make up`, `make test`, `make lint`, …). The Makefile is optional; on Windows without `make`, use the `docker compose` commands directly.

## Catalog, storage and images (Phase 3)

Catalog management is open to **content staff** and the **Super Admin** (لوحة الإدارة ← الأعمال الفنية / الفنانون / التصنيفات). Other roles and customers get 403 from the API and 404 pages.

Images go to S3-compatible object storage through django-storages (ADR-17):

- The uploaded original is validated by its content (JPEG/PNG/WebP, size, pixel count, at least 300 px on the short side) and stored in the **private** bucket, untouched.
- A Celery task on the `media` queue renders WebP variants (400/1000/2000 px wide, never upscaled or cropped, all metadata including GPS stripped) into the **public** bucket. The admin UI polls until the image is ready.
- Artworks can only be published once their primary image is ready (BR-103). Problems are explained in the admin panel.

In development the `storage` service (SeaweedFS) runs inside Compose. `migrate` creates both buckets (`ensure_buckets`), and nginx serves public variants read-only at `/media/`. The development credentials live in `infra/seaweedfs/s3.dev.json` and are for local use only.

In production, set `S3_ENDPOINT_URL`, the keys and `MEDIA_PUBLIC_BASE_URL` for your provider. To self-host SeaweedFS instead, copy `infra/seaweedfs/s3.dev.json` to `infra/seaweedfs/s3.json` (gitignored), set strong keys, and start Compose with `--profile self-hosted-storage`. See `infra/seaweedfs/README.md`.

## Offers, search and favorites (Phase 4)

- **Offers (listings)**: from the artwork editor (**العرض التجاري**), staff create a fixed-price offer: a unique piece, a limited quantity, or unlimited. Only the Super Admin sets the price, the commission and the deposit (BR-212). An offer cannot be activated before that, and the database refuses it too. An artwork has at most one active offer. Withdrawn or ended offers stay as history.
- **Platform defaults** (**لوحة الإدارة ← إعدادات المنصة**): the default commission and deposit, the WhatsApp number and the pending-order limit. Staff can read them; only the Super Admin can change them.
- **Search**: `/artworks?q=…` matches the title, creator, description, category, materials, techniques and tags. Arabic spelling variants match (أ/إ/آ/ا, ى/ي, ة/ه, tashkeel). Filters: category, artist, price range, availability, sale mode, materials and techniques. The search uses PostgreSQL `pg_trgm`, which the migration enables (`CREATE EXTENSION`). On a managed database, make sure the migration user may create extensions, or enable `pg_trgm` once by hand.
- **Favorites**: the heart button on cards and artwork pages, plus `/favorites`.
- Public catalogue pages are cached for 60 seconds, so a new price shows up within a minute. Checkout (Phase 5) always re-checks price and stock on the server.

## Cart and orders (Phase 5)

Workflow and UX analysis: `docs/ux/PHASE5_CART_ORDERS.md`.

- **Customers** add fixed-price offers to the cart, which does not reserve stock. Checkout creates one order and reserves the stock for 24 hours until the deposit is paid. The customer must accept the deposit and cancellation policy; the accepted version is stored with the order. The order page shows a countdown (from the server clock) and a WhatsApp deep link to arrange payment; set the number in **إعدادات المنصة**.
- **Operations staff and the Super Admin** manage orders in **لوحة الإدارة ← الطلبات**: they record payments (deposit, payment, refund), and the order advances automatically as money is confirmed. They also manage delivery, completion, cancellation and internal notes. Removing an item is possible before the deposit. Custom deposits are for the Super Admin only.
- Staff accounts cannot buy. They see prices with a note instead of a buy button.
- Checkout and payment recording take an `Idempotency-Key` header, so retries never create duplicates.
- Expired reservations are released by Celery Beat every minute, and also lazily before any action on an order.

## Auctions and auction requests (Phase 6)

Workflow and UX analysis: `docs/ux/PHASE6_AUCTIONS.md`.

- **Auction managers and the Super Admin** create auctions in **لوحة الإدارة ← المزادات** for a published artwork that has no active offer, save a draft, then schedule it. Terms (prices, hidden reserve, extension rule, winner deposit 50–100%, non-payment policy) can change only before the start.
- **Bidding** is an HTTP request with an `Idempotency-Key`. The server locks the auction row and decides with the PostgreSQL clock, so no bid is accepted after the end even if the scheduler is late. A bid in the last minutes extends the auction (capped).
- **Live updates** go over `/ws/auctions/<id>/` (snapshot + ordered events with `seq`; clients resync over REST after a gap or reconnect). Outbid and win notices go to `/ws/me/` and appear on any page.
- **The winner** gets an auction order with a deposit of at least 50% due within one hour. A confirmed deposit awards the auction; an unpaid one goes to the next bidder or ends the auction, per the auction's policy. Celery Beat runs `auction_tick` every 5 seconds; reads also apply due transitions.
- **Customers** offer their own works through **طلبات المزاد**. Staff review, ask for more information, record the agreed platform share (required before approval), create the artwork for the owner, then the auction.
- While an auction is open, its manager can **void a bid** from the live monitor with a required reason (BR-509). The bid stays in the record; if it led, the lead returns to the best remaining bid. Bidders see the change live and the affected bidders are notified.
- Auction managers see the auction orders (only) on the order desk.

## Commissions, settlements, dashboard and audit (Phase 7a)

Workflow and UX analysis: `docs/ux/PHASE7A_FINANCE.md`.

- **Commission (BR-701)**: the listing's own rate, else the artist's active agreement, else the platform default. The Super Admin manages agreements on the artist page (a new one ends the current one). Orders keep the rate from when they were placed.
- **Settlements (BR-704…706)**: one per sold item, created automatically when an order is confirmed (`apps.settlements`, via the `order_status_changed` signal). Operations staff and the Super Admin see what each payee is owed, record one transfer per payee with its reference, and can hold or cancel with a reason. A migration created settlements for orders confirmed earlier.
- **Dashboard**: the admin home shows KPIs for the sections each role works in, plus a "needs attention" list.
- **Audit log**: the Super Admin browses every administrative and financial action in **لوحة الإدارة ← سجل التدقيق**.

## Run without Docker

You need Python 3.12+, Node 22.12+, PostgreSQL 16 and Redis 7 running locally.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements/dev.txt
cat > .env <<'EOF'
DJANGO_SECRET_KEY=local-dev-only-0123456789abcdefghijklmnopqrstuvwxyz
DATABASE_URL=postgres://USER:PASSWORD@127.0.0.1:5432/damascene
REDIS_CACHE_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CHANNEL_LAYER_URL=redis://127.0.0.1:6379/2
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:3000
EOF
python manage.py migrate
python manage.py runserver 8000                                   # REST API
uvicorn config.asgi:application --port 8001 --reload              # WebSockets (second terminal)
celery -A config worker -Q critical,default,media,notifications -l INFO   # third terminal
celery -A config beat -l INFO                                     # fourth terminal

# Frontend
cd frontend
npm ci
NEXT_PUBLIC_CSRF_COOKIE_NAME=csrftoken INTERNAL_API_URL=http://localhost:8000 npm run dev
```

Without nginx, the browser does not have the single origin, so use the Docker setup for anything that involves cookies or WebSockets.

---

## Tests and quality checks

```bash
# Backend (needs PostgreSQL; Redis only for tests marked `redis`)
cd backend
pytest                              # unit + integration suite (Redis mocked in-memory)
REDIS_INTEGRATION=1 pytest          # also run against real Redis
ruff check . && ruff format --check .
lint-imports                        # architecture contracts (domain ↛ realtime/channels)
python manage.py makemigrations --check --dry-run

# Frontend
cd frontend
npm test          # vitest
npm run lint      # eslint, including the RTL rule (no ml-/mr-/left-/right-/text-left …)
npm run typecheck # next typegen + tsc --noEmit
npm run build
```

Tests run against a real PostgreSQL database. Row locks and constraints must behave exactly as they do in production. Run the tests and migrations against PostgreSQL directly, not through PgBouncer (see `IMPLEMENTATION_LOG.md`).

### API contract

The backend's OpenAPI schema is committed in `backend/openapi/schema.yml`, and the frontend types are generated from it. After changing an endpoint:

```bash
cd backend && python manage.py spectacular --file openapi/schema.yml --validate --fail-on-warn
cd ../frontend && npm run gen:api
```

CI fails if either file is out of date.

---

## Configuration

All configuration comes from environment variables (`backend/config/settings/base.py`). `.env.example` documents the variables used in local development.

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Required. Must be long and random in production. |
| `DATABASE_URL` | App traffic goes through PgBouncer (`pgbouncer:6432`). Migrations connect to PostgreSQL directly. |
| `REDIS_CACHE_URL`, `CELERY_BROKER_URL`, `CHANNEL_LAYER_URL` | Kept separate on purpose, so each can be moved to its own Redis later. |
| `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Required in production. They also gate WebSocket `Origin`. |
| `SESSION_COOKIE_NAME` / `CSRF_COOKIE_NAME` | `__Host-sid` / `__Host-csrf` in production. Dev uses `sid` / `csrftoken`, because `__Host-` cookies require HTTPS. |
| `DJANGO_ADMIN_PATH` | Path of the internal Django admin (default `internal-admin/`). |
| `LOG_LEVEL`, `LOG_FORMAT` | Log format is `json` in production and `console` in dev. |
| `OTP_SENDER` | `console` (dev) or `disabled` (prod default until WhatsApp is set up). |
| `NUM_PROXIES` | Trusted reverse proxies in front of Django (default 1 = nginx); used for client IPs in rate limits. |
| `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | S3-compatible object storage (SeaweedFS in dev, ADR-17). |
| `S3_PUBLIC_BUCKET`, `S3_PRIVATE_BUCKET` | Public image variants / private originals (defaults `damascene-public`, `damascene-private`). |
| `MEDIA_PUBLIC_BASE_URL` | Public URL prefix for image variants (dev `http://localhost:8080/media`; prod your CDN or media domain). |
| `IMAGE_UPLOAD_MAX_BYTES` | Upload size limit (default 15 MB). |

## Production (Docker Compose on one host)

`docker-compose.prod.yml` runs the same images with Gunicorn (WSGI) for `api`, Gunicorn + Uvicorn workers (ASGI) for `realtime`, and nginx with TLS. The server's `.env` must additionally define:

`REDIS_PASSWORD` (and the Redis URLs must include it, e.g. `redis://:PASSWORD@redis:6379/0`), `SERVER_NAME`, `MEDIA_ORIGIN`, `TLS_CERT_DIR` (a directory containing `fullchain.pem` and `privkey.pem`), and production values for `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (`https://your-domain`).

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The full deployment guide (TLS issuance, backups with WAL/PITR, monitoring) is written in Phase 9. Choosing the hosting provider is an open decision (PRD Q2), and the provider must support WebSockets.
