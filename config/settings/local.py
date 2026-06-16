import logging
import os

from .base import *  # noqa: F403

logger = logging.getLogger(__name__)

DEBUG = True
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-dev-only-change-me-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
)
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]  # noqa: S104

OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "default-client-id")
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", "default-client-secret")
OIDC_DISCOVERY_URL = os.environ.get(
    "OIDC_DISCOVERY_URL",
    "https://test.example.com/.well-known/openid-configuration",
)

if (
    OIDC_CLIENT_ID == "default-client-id"
    or OIDC_CLIENT_SECRET == "default-client-secret"  # noqa: S105
    or OIDC_DISCOVERY_URL == "https://test.example.com/.well-known/openid-configuration"
):
    logger.warning("One of the OIDC envs is not set; login flow will not work against a real provider")

SKIP_OIDC = os.environ.get("SKIP_OIDC", "false").lower() == "true"
if SKIP_OIDC:
    MIDDLEWARE = [m for m in MIDDLEWARE if m != "django.contrib.auth.middleware.LoginRequiredMiddleware"]  # noqa: F405
    MIDDLEWARE.append("rijksprofielservice.rijksauth.middleware.AutoLoginMiddleware")  # noqa: F405

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "rijksprofielservice": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
