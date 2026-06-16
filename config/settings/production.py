import os

from .base import *  # noqa: F403
from .base import DATABASES

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
_allowed_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = _allowed_hosts.split(",") if _allowed_hosts else []

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "true").lower() != "false"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_NAME = "__Secure-sessionid"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_NAME = "__Secure-csrftoken"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

_WHITENOISE = "whitenoise.middleware.WhiteNoiseMiddleware"
_AFTER_SECURITY = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1  # noqa: F405
MIDDLEWARE.insert(_AFTER_SECURITY, _WHITENOISE)  # noqa: F405

DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

OIDC_CLIENT_ID = os.environ["OIDC_CLIENT_ID"]
OIDC_CLIENT_SECRET = os.environ["OIDC_CLIENT_SECRET"]
OIDC_DISCOVERY_URL = os.environ["OIDC_DISCOVERY_URL"]
