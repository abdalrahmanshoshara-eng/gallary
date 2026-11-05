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
    "django.contrib.postgres",
    # Third party
    "channels",
    "rest_framework",
    "drf_spectacular",
    "django_celery_beat",
    # Project
    "apps.core",
    "apps.accounts",
    "apps.audit",
    "apps.media",
    "apps.catalog",
    "apps.artists",
    "apps.artworks",
    "apps.listings",
    "apps.favorites",
    "apps.cart",
    "apps.orders",
    "apps.auctions",
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
    "apps.accounts.middleware.SessionPolicyMiddleware",
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
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "apps.accounts.passwords.LetterAndDigitValidator"},
]

# Password login lockout (per phone and per client IP, rolling window).
LOGIN_MAX_FAILURES_PER_PHONE = env.int("LOGIN_MAX_FAILURES_PER_PHONE", default=5)
LOGIN_MAX_FAILURES_PER_IP = env.int("LOGIN_MAX_FAILURES_PER_IP", default=30)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=15 * 60)

# Default Super Admin, created by `ensure_super_admin` (run by the migrate service) when the
# phone has no account yet. Production refuses the development password (prod.py).
DEFAULT_SUPER_ADMIN_PHONE = env.str("DEFAULT_SUPER_ADMIN_PHONE", default="0943959774")
DEFAULT_SUPER_ADMIN_PASSWORD = env.str("DEFAULT_SUPER_ADMIN_PASSWORD", default="admin123456")
DEFAULT_SUPER_ADMIN_NAME = env.str("DEFAULT_SUPER_ADMIN_NAME", default="المدير العام")

# ---------------------------------------------------------------------------
# Authentication — phone + OTP (BR-901…910). No MFA in the MVP (BR-907).
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

# "console" (development only), "disabled" (default until the WhatsApp service is
# subscribed — BR-901c). A WhatsApp sender is added as a new class + setting value.
OTP_SENDER = env.str("OTP_SENDER", default="disabled")
OTP_SENDERS = {
    "disabled": "apps.accounts.otp.senders.DisabledSender",
    "console": "apps.accounts.otp.senders.ConsoleSender",
}
OTP_LENGTH = 6
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=300)
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = env.int("OTP_RESEND_COOLDOWN_SECONDS", default=60)
OTP_MAX_PER_PHONE_PER_HOUR = env.int("OTP_MAX_PER_PHONE_PER_HOUR", default=5)
OTP_MAX_PER_IP_PER_HOUR = env.int("OTP_MAX_PER_IP_PER_HOUR", default=20)
PHONE_DEFAULT_REGION = env.str("PHONE_DEFAULT_REGION", default="SY")

# Session policy (BR-908). Customer sessions slide; staff sessions are short.
CUSTOMER_SESSION_SECONDS = 60 * 60 * 24 * 30
STAFF_SESSION_ABSOLUTE_SECONDS = 60 * 60 * 12
STAFF_SESSION_IDLE_SECONDS = 60 * 30
# How often last-seen is written to the database and revocation re-checked there.
SESSION_TOUCH_INTERVAL_SECONDS = 300

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

# Object storage (S3-compatible, ADR-17). Only object keys are stored in the database, so
# the provider or the CDN can change without data migration (ARCHITECTURE §9).
#   public  bucket: processed image variants, served anonymously through the media URL/CDN
#   private bucket: original uploads (may contain EXIF/GPS) and private documents
S3_ENDPOINT_URL = env.str("S3_ENDPOINT_URL", default=None)
S3_REGION = env.str("S3_REGION", default="us-east-1")
S3_ACCESS_KEY_ID = env.str("S3_ACCESS_KEY_ID", default=None)
S3_SECRET_ACCESS_KEY = env.str("S3_SECRET_ACCESS_KEY", default=None)
S3_PUBLIC_BUCKET = env.str("S3_PUBLIC_BUCKET", default="damascene-public")
S3_PRIVATE_BUCKET = env.str("S3_PRIVATE_BUCKET", default="damascene-private")
# Browser-facing base URL of the public bucket, e.g. http://localhost:8080/media (dev,
# proxied by nginx) or https://media.example.com (CDN in production).
MEDIA_PUBLIC_BASE_URL = env.str("MEDIA_PUBLIC_BASE_URL", default="http://localhost:8080/media").rstrip("/")

_media_scheme, _, _media_host = MEDIA_PUBLIC_BASE_URL.partition("://")
_S3_COMMON = {
    "endpoint_url": S3_ENDPOINT_URL,
    "region_name": S3_REGION,
    "access_key": S3_ACCESS_KEY_ID,
    "secret_key": S3_SECRET_ACCESS_KEY,
    "addressing_style": "path",
    "signature_version": "s3v4",
    "default_acl": None,
    "file_overwrite": False,
}

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_S3_COMMON,
            "bucket_name": S3_PUBLIC_BUCKET,
            "custom_domain": _media_host,
            "url_protocol": f"{_media_scheme}:",
            "querystring_auth": False,
            # Variant keys are content-addressed (new upload = new key), so they never change.
            "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},
        },
    },
    "private": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_S3_COMMON,
            "bucket_name": S3_PRIVATE_BUCKET,
            "querystring_auth": True,
            "querystring_expire": 300,
        },
    },
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Image uploads (BR-108).
IMAGE_UPLOAD_MAX_BYTES = env.int("IMAGE_UPLOAD_MAX_BYTES", default=15 * 1024 * 1024)
IMAGE_MIN_SIDE_PX = 300
IMAGE_MAX_PIXELS = 60_000_000  # decompression-bomb guard
IMAGE_VARIANT_WIDTHS = (400, 1000, 2000)
IMAGE_VARIANT_QUALITY = 82
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

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
        # Burst protection; the durable OTP limits (BR-904) are enforced in the database.
        "login": env.str("THROTTLE_LOGIN", default="20/min"),
        "register": env.str("THROTTLE_REGISTER", default="10/hour"),
        "checkout": env.str("THROTTLE_CHECKOUT", default="20/hour"),
        "bids": env.str("THROTTLE_BIDS", default="30/min"),
        "otp_request": env.str("THROTTLE_OTP_REQUEST", default="10/min"),
        "otp_verify": env.str("THROTTLE_OTP_VERIFY", default="30/min"),
    },
    # Number of trusted reverse proxies in front of Django (nginx = 1). Used to read the
    # client IP from X-Forwarded-For for throttling and OTP limits.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=1),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
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
    "ENUM_NAME_OVERRIDES": {
        "ArchiveVisibilityEnum": "apps.artworks.models.ArchiveVisibility",
        "PublicationStatusEnum": "apps.artworks.models.PublicationStatus",
        "ArtistStatusEnum": "apps.artists.models.ArtistStatus",
        "ImageStatusEnum": "apps.media.models.ImageStatus",
        "DepositTypeEnum": "apps.core.models.DepositType",
        "ListingStatusEnum": "apps.listings.models.ListingStatus",
        "QuantityModeEnum": "apps.listings.models.QuantityMode",
        "SaleModeEnum": "apps.listings.models.SaleMode",
        "OrderStatusEnum": "apps.orders.models.OrderStatus",
        "DeliveryStatusEnum": "apps.orders.models.DeliveryStatus",
        "DeliveryMethodEnum": "apps.orders.models.DeliveryMethod",
        "PaymentKindEnum": "apps.orders.models.PaymentKind",
        "PaymentMethodEnum": "apps.orders.models.PaymentMethod",
        "PaymentRecordStatusEnum": "apps.orders.models.PaymentRecordStatus",
        "OrderItemStatusEnum": "apps.orders.models.OrderItemStatus",
        "GovernorateEnum": "apps.accounts.models.Governorate",
        "AuctionStatusEnum": "apps.auctions.models.AuctionStatus",
        "AuctionOutcomeEnum": "apps.auctions.models.AuctionOutcome",
        "BidStatusEnum": "apps.auctions.models.BidStatus",
        "NonPaymentPolicyEnum": "apps.auctions.models.NonPaymentPolicy",
        "AuctionRequestStatusEnum": "apps.auctions.models.RequestStatus",
        "NoteVisibilityEnum": "apps.auctions.models.NoteVisibility",
    },
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
# Do not turn print() output into log records: the dev OTP console sender writes to raw
# stdout on purpose so codes never enter log pipelines.
CELERY_WORKER_REDIRECT_STDOUTS = False
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "scheduler-heartbeat": {
        "task": "apps.core.tasks.scheduler_heartbeat",
        "schedule": 60.0,
        "options": {"queue": "critical", "expires": 55},
    },
    "expire-due-orders": {
        "task": "apps.orders.tasks.expire_due_orders",
        "schedule": 60.0,
        "options": {"queue": "critical", "expires": 55},
    },
    # Auction start/end/winner-deadline transitions (BR-505, 511, 514); reads also apply them lazily.
    "auction-tick": {
        "task": "apps.auctions.tasks.auction_tick",
        "schedule": 5.0,
        "options": {"queue": "critical", "expires": 4},
    },
    "end-expired-listings": {
        "task": "apps.listings.tasks.end_expired_listings",
        "schedule": 60.0,
        "options": {"queue": "default", "expires": 55},
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
    "apps.media.health.check_storage",
]
# Checks that report "degraded" without failing readiness. Storage only affects uploads
# and new images (pages keep working from the CDN), so it does not take the API down.
HEALTH_NON_CRITICAL = {"scheduler", "storage"}

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
