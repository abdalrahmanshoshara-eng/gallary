"""Local development (docker compose). Never used in production."""

from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# Development runs over plain HTTP behind the local nginx, so the __Host- cookie prefix
# (which requires Secure) is replaced with plain names. Production keeps __Host-.
SESSION_COOKIE_NAME = env.str("SESSION_COOKIE_NAME", default="sid")
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_NAME = env.str("CSRF_COOKIE_NAME", default="csrftoken")
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)

LOG_FORMAT = env.str("LOG_FORMAT", default="console")
LOGGING["handlers"]["stdout"]["formatter"] = LOG_FORMAT

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]
SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.AllowAny"]

STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}

# Serve static files from app directories without collectstatic (no STATIC_ROOT scan).
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
