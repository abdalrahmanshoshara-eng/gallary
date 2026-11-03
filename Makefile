# Developer shortcuts. Every target wraps a plain command documented in README.md.
COMPOSE ?= docker compose
BACKEND = $(COMPOSE) run --rm --no-deps api
# Commands that need the database run inside the running api container.
BACKEND_LIVE = $(COMPOSE) exec api

.PHONY: help env up down logs ps migrate makemigrations superuser shell test test-backend test-frontend lint lint-backend lint-frontend schema check

help: ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

env: ## Create .env from the template (once)
	@test -f .env || cp .env.example .env && echo ".env ready"

up: env ## Build and start the full stack (http://localhost:8080)
	$(COMPOSE) up -d --build

down: ## Stop the stack (data volumes are kept)
	$(COMPOSE) down

logs: ## Follow logs of all services
	$(COMPOSE) logs -f --tail=100

ps: ## Service status and health
	$(COMPOSE) ps

migrate: ## Apply database migrations
	$(COMPOSE) run --rm migrate

makemigrations: ## Create migrations after model changes
	$(BACKEND_LIVE) python manage.py makemigrations

superuser: ## Create an internal-admin superuser
	$(BACKEND_LIVE) python manage.py createsuperuser

shell: ## Django shell
	$(BACKEND_LIVE) python manage.py shell

test: test-backend test-frontend ## Run all tests

test-backend: ## Backend tests (needs the postgres service running)
	$(COMPOSE) run --rm -e DATABASE_URL=postgres://$${POSTGRES_USER:-damascene}:$${POSTGRES_PASSWORD:-change-me-local-only}@postgres:5432/$${POSTGRES_DB:-damascene} -e REDIS_INTEGRATION=1 api pytest

test-frontend: ## Frontend unit tests
	$(COMPOSE) run --rm --no-deps web npm test

lint: lint-backend lint-frontend ## All linters

lint-backend: ## ruff + import contracts + migrations check
	$(BACKEND) sh -c "ruff check . && ruff format --check . && lint-imports && python manage.py makemigrations --check --dry-run"

lint-frontend: ## eslint + typecheck
	$(COMPOSE) run --rm --no-deps web sh -c "npm run lint && npm run typecheck"

schema: ## Regenerate the OpenAPI schema and frontend types
	$(BACKEND) python manage.py spectacular --file openapi/schema.yml --validate --fail-on-warn
	$(COMPOSE) run --rm --no-deps web npm run gen:api
