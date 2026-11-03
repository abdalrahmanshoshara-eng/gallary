"""
Base settings shared by every environment.

All configuration comes from environment variables (Twelve-Factor). No secrets live in
this file. Environment-specific modules (dev, test, prod) import from here and override
only what differs.
"""

from __future__ import annotations

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Optional local file for running outside Docker; never committed (see .gitignore).
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
APP_ENV = env.str("APP_ENV", default="development")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "channels",
    "rest_framework",
    "drf_spectacular",
    "django_celery_beat",
    # Project
    "apps.core",
    "apps.accounts",
    "apps.realtime",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Path of the internal Django admin (helper tool only, ADR-07). Not the default "admin/".
DJANGO_ADMIN_PATH = env.str("DJANGO_ADMIN_PATH", default="internal-admin/")

# ---------------------------------------------------------------------------
# Database — PostgreSQL through PgBouncer in transaction-pooling mode (ADR-15)
# ---------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=0)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
# Server-side cursors are incompatible with transaction pooling.
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = env.bool("DATABASE_DISABLE_SERVER_SIDE_CURSORS", default=True)
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"]["connect_timeout"] = env.int("DATABASE_CONNECT_TIMEOUT", default=5)
# psycopg 3 prepares statements server-side after N executions; prepared statements do not
# survive transaction pooling (the next transaction may run on another server connection).
DATABASES["default"]["OPTIONS"]["prepare_threshold"] = None

# ---------------------------------------------------------------------------
# Redis — three separately configurable URLs (ARCHITECTURE §7.7)
# ---------------------------------------------------------------------------
REDIS_CACHE_URL = env.str("REDIS_CACHE_URL")
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL")
CHANNEL_LAYER_URL = env.str("CHANNEL_LAYER_URL")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
        "KEY_PREFIX": "da",
        "TIMEOUT": 300,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [CHANNEL_LAYER_URL],
            "prefix": "da:ch",
            "capacity": 1500,
            "expiry": 60,
        },
    }
}

# ---------------------------------------------------------------------------
# Sessions, CSRF and security (ADR-01, ADR-06, BR-906)
# ---------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_NAME = env.str("SESSION_COOKIE_NAME", default="__Host-sid")
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # customer maximum; staff policy applied in Phase 2
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_DOMAIN = None  # host-only cookie (required by the __Host- prefix)

CSRF_COOKIE_NAME = env.str("CSRF_COOKIE_NAME", default="__Host-csrf")
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
CSRF_COOKIE_HTTPONLY = False  # the frontend reads it to send X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=True)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation — stored in UTC, displayed in Damascus time by the frontend
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "ar"
LANGUAGES = [("ar", "العربية")]
TIME_ZONE = "UTC"
DISPLAY_TIME_ZONE = "Asia/Damascus"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static and media files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Object storage (S3-compatible). Only keys are stored in the database (ARCHITECTURE §9).
AWS_S3_ENDPOINT_URL = env.str("S3_ENDPOINT_URL", default=None)
AWS_S3_REGION_NAME = env.str("S3_REGION", default="us-east-1")
AWS_ACCESS_KEY_ID = env.str("S3_ACCESS_KEY_ID", default=None)
AWS_SECRET_ACCESS_KEY = env.str("S3_SECRET_ACCESS_KEY", default=None)
AWS_STORAGE_BUCKET_NAME = env.str("S3_PUBLIC_BUCKET", default="damascene-public")
AWS_S3_CUSTOM_DOMAIN = env.str("S3_PUBLIC_CUSTOM_DOMAIN", default=None)
AWS_S3_ADDRESSING_STYLE = env.str("S3_ADDRESSING_STYLE", default="path")
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = False
AWS_S3_FILE_OVERWRITE = False
S3_PRIVATE_BUCKET = env.str("S3_PRIVATE_BUCKET", default="damascene-private")

STORAGES = {
    "default": {"BACKEND": "storages.backends.s3.S3Storage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Secure by default: every endpoint must opt in to public access explicitly.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env.str("THROTTLE_ANON", default="120/min"),
        "user": env.str("THROTTLE_USER", default="600/min"),
    },
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Damascene Art Platform API",
    "DESCRIPTION": "REST API لمنصة الفن الدمشقية",
    "VERSION": "1.0.0",
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}

# ---------------------------------------------------------------------------
# Celery (ARCHITECTURE §7.5)
# ---------------------------------------------------------------------------
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES_NAMES = ("critical", "default", "media", "notifications")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 3600}
# Keep Django LOGGING (JSON, request_id, redaction) for worker and beat output.
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "scheduler-heartbeat": {
        "task": "apps.core.tasks.scheduler_heartbeat",
        "schedule": 60.0,
        "options": {"queue": "critical", "expires": 55},
    },
}
# Seconds after which a missing scheduler heartbeat is reported as degraded.
SCHEDULER_HEARTBEAT_STALE_AFTER = 180

# ---------------------------------------------------------------------------
# Domain events (ADR-05v2) — the realtime app subscribes; domain code never imports it
# ---------------------------------------------------------------------------
EVENT_BUS_BACKEND = env.str("EVENT_BUS_BACKEND", default="apps.realtime.publisher.ChannelsEventBus")

# ---------------------------------------------------------------------------
# Health checks — each entry is a dotted path to a callable returning CheckResult
# ---------------------------------------------------------------------------
HEALTH_CHECKS = [
    "apps.core.health.check_database",
    "apps.core.health.check_cache",
    "apps.core.health.check_broker",
    "apps.core.health.check_scheduler",
    "apps.realtime.health.check_channel_layer",
]
# Checks that report "degraded" without failing readiness.
HEALTH_NON_CRITICAL = {"scheduler"}

# ---------------------------------------------------------------------------
# Logging — JSON lines with request_id, sensitive fields redacted
# ---------------------------------------------------------------------------
LOG_LEVEL = env.str("LOG_LEVEL", default="INFO")
LOG_FORMAT = env.str("LOG_FORMAT", default="json")  # "json" | "console"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.core.logging.RequestIdFilter"},
        "redact": {"()": "apps.core.logging.SensitiveDataFilter"},
    },
    "formatters": {
        "json": {
            "()": "apps.core.logging.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
        },
        "console": {
            "format": "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": LOG_FORMAT,
            "filters": ["request_id", "redact"],
        },
    },
    "root": {"handlers": ["stdout"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": False},
        "django.server": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": False},
        "apps": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": False},
    },
}
