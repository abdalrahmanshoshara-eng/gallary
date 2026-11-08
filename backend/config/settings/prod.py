"""Production settings. Every value comes from the environment; unsafe defaults fail fast."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env

DEBUG = False

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must be set in production.")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a long random value in production.")
if not (SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE):
    raise ImproperlyConfigured("Session and CSRF cookies must be Secure in production.")

if OTP_SENDER == "console":
    raise ImproperlyConfigured("OTP_SENDER=console is for development only (BR-901c).")

if NOTIFICATIONS_EMAIL_ENABLED:
    if EMAIL_BACKEND.rsplit(".", 2)[-2] in {"console", "locmem", "filebased", "dummy"}:
        raise ImproperlyConfigured("Notification e-mail needs a real EMAIL_BACKEND in production (e.g. SMTP).")
    if EMAIL_BACKEND.endswith("smtp.EmailBackend") and not EMAIL_HOST:
        raise ImproperlyConfigured("NOTIFICATIONS_EMAIL_ENABLED requires EMAIL_HOST (SMTP server).")
    if not SITE_URL.startswith("https://"):
        raise ImproperlyConfigured("SITE_URL must be the public https:// address for links in e-mails.")

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
# Health probes from the internal network arrive over plain HTTP.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/"]
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=63072000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
