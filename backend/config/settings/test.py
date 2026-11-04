"""
Test settings.

Tests run against a real PostgreSQL (row locks and constraints must behave exactly as in
production). Redis-dependent pieces are replaced with in-memory equivalents so the unit
suite does not need Redis; integration tests marked `redis` use the real services.
"""

from .base import *  # noqa: F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EVENT_BUS_BACKEND = "apps.core.events.InMemoryEventBus"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage", "OPTIONS": {"base_url": "http://media.test/"}},
    "private": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

SESSION_COOKIE_NAME = "sid"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_SECURE = False

LOG_LEVEL = env.str("LOG_LEVEL", default="WARNING")
LOGGING["root"]["level"] = LOG_LEVEL
for _logger in LOGGING["loggers"].values():
    _logger["level"] = LOG_LEVEL

# Serve static files from app directories without collectstatic (no STATIC_ROOT scan).
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True

OTP_SENDER = "console"
REST_FRAMEWORK["NUM_PROXIES"] = 0

HEALTH_CHECKS = [c for c in HEALTH_CHECKS if not c.endswith("check_storage")]
