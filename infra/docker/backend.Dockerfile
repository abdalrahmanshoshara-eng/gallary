# syntax=docker/dockerfile:1.7
# One image for every backend process type: api, realtime, worker, beat, migrate (ARCHITECTURE §2).
# The process is selected by the container command.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app

# ---- dependencies --------------------------------------------------------------------
FROM base AS deps-prod
COPY backend/requirements/base.txt backend/requirements/prod.txt /tmp/requirements/
RUN pip install -r /tmp/requirements/prod.txt

FROM deps-prod AS deps-dev
COPY backend/requirements/dev.txt /tmp/requirements/
RUN pip install -r /tmp/requirements/dev.txt

# ---- development (source is bind-mounted by docker compose) ---------------------------
FROM deps-dev AS dev
ENV DJANGO_SETTINGS_MODULE=config.settings.dev
USER app
ENTRYPOINT ["tini", "--"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---- production -------------------------------------------------------------------------
FROM deps-prod AS prod
COPY --chown=app:app backend/ /app/
# collectstatic needs importable settings; these throwaway values exist only at build time.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_SECRET_KEY=build-only-collectstatic-key-not-used-at-runtime-0123456789abcdef \
    DJANGO_ALLOWED_HOSTS=build \
    CSRF_TRUSTED_ORIGINS=https://build \
    DATABASE_URL=postgres://build:build@build:5432/build \
    REDIS_CACHE_URL=redis://build:6379/0 \
    CELERY_BROKER_URL=redis://build:6379/1 \
    CHANNEL_LAYER_URL=redis://build:6379/2 \
    python manage.py collectstatic --noinput -v0 \
    && chown -R app:app /app/staticfiles
ENV DJANGO_SETTINGS_MODULE=config.settings.prod
USER app
EXPOSE 8000 8001
ENTRYPOINT ["tini", "--"]
CMD ["gunicorn", "-c", "config/gunicorn/api.py", "config.wsgi:application"]
