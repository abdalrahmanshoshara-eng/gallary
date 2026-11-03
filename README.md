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

**Current status:** Phase 1 (Foundation) is complete. No business features yet — see `FEATURE_CHECKLIST.md`.

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
docker compose run --rm --no-deps api python manage.py createsuperuser   # internal admin at /internal-admin/
docker compose down                                 # stop (data volumes are kept)
```

The scheduler check reports `degraded` until Celery beat completes its first one-minute heartbeat. That is expected right after startup.

`make help` lists shortcuts for the same commands (`make up`, `make test`, `make lint`, …). The Makefile is optional; on Windows without `make`, use the `docker compose` commands directly.

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
| `S3_*` | S3-compatible object storage. Used from Phase 3. |

## Production (Docker Compose on one host)

`docker-compose.prod.yml` runs the same images with Gunicorn (WSGI) for `api`, Gunicorn + Uvicorn workers (ASGI) for `realtime`, and nginx with TLS. The server's `.env` must additionally define:

`REDIS_PASSWORD` (and the Redis URLs must include it, e.g. `redis://:PASSWORD@redis:6379/0`), `SERVER_NAME`, `MEDIA_ORIGIN`, `TLS_CERT_DIR` (a directory containing `fullchain.pem` and `privkey.pem`), and production values for `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (`https://your-domain`).

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The full deployment guide (TLS issuance, backups with WAL/PITR, monitoring) is written in Phase 9. Choosing the hosting provider is an open decision (PRD Q2), and the provider must support WebSockets.
#   g a l l a r y  
 