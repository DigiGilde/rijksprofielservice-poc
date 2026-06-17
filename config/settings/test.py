"""Test settings: fast password hasher, no OIDC, SQLite in-memory."""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ALLOWED_HOSTS = ["localhost", "testserver"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

OIDC_CLIENT_ID = None
OIDC_CLIENT_SECRET = None
OIDC_DISCOVERY_URL = None

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
