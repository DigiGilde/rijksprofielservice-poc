"""Django settings for rijksprofielservice (base)."""

import os
from pathlib import Path

from django.utils.translation import gettext_lazy

BASE_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = BASE_DIR / "rijksprofielservice"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "rest_framework",
    "oauth2_provider",
    "rijksprofielservice.rijksauth",
    "rijksprofielservice.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "APP_DIRS": True,
        "OPTIONS": {
            "environment": "config.jinja2.environment",
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
    {
        # Django admin needs DTL templates.
        "BACKEND": "django.template.backends.django.DjangoTemplates",
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "rijksprofielservice"),
        "USER": os.environ.get("POSTGRES_USER", "rijksprofielservice"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "rijksprofielservice"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "nl-nl"
LANGUAGES = [("nl", gettext_lazy("Nederlands"))]
TIME_ZONE = "Europe/Amsterdam"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

SESSION_COOKIE_AGE = 8 * 60 * 60

LOGIN_URL = "login"

AUTHENTICATION_BACKENDS = [
    "rijksprofielservice.rijksauth.auth_backend.AuthBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_USER_MODEL = "rijksauth.User"

# Uniqueness enforced via Lower("email") constraint, not field-level unique.
SILENCED_SYSTEM_CHECKS = ["auth.W004"]

AUTH_NO_ACCESS_URL = "/geen-toegang/"

OIDC_ID_TOKEN_SESSION_KEY = "oidc_id_token"  # noqa: S105 — session key, niet een secret
# TODO: generaliseren naar upstream rijksauth (Wies-repo). Voor nu lokaal toegevoegd
# zodat core de Keycloak `sub` op UserProfile.sso_subject kan zetten na login.
OIDC_SUBJECT_SESSION_KEY = "oidc_subject"  # noqa: S105 — session key, niet een secret
OIDC_POST_LOGOUT_COOKIE_NAME = "rijksprofielservice_post_logout"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
    ],
    # TokenHasScope ipv IsAuthenticated: client-credentials tokens hebben `user=None`,
    # die zou IsAuthenticated weigeren. TokenHasScope checkt expiry + scope op token.
    "DEFAULT_PERMISSION_CLASSES": [
        "oauth2_provider.contrib.rest_framework.TokenHasScope",
    ],
    "UNAUTHENTICATED_USER": None,
}

# Mock consuming-app client_secrets — alleen voor de demo-landings (server-side
# token-exchange en M2M-grants). Productie-clients hebben hun eigen secret-storage.
MOCK_CLIENT_SECRETS = {
    "mock-wies": "local-dev-secret-wies",
    "mock-wies-m2m": "local-dev-secret-wies",
    "mock-amt": "local-dev-secret-amt",
    "mock-amt-m2m": "local-dev-secret-amt",
}

# OAuth Authorization Server (django-oauth-toolkit). Profielservice is zelf de AS;
# één scope ('read_profile') — field-filtering blijft in fields_for_app_and_user.
# `http` toegestaan voor localhost demo; productie zet dit naar `["https"]`.
OAUTH2_PROVIDER = {
    "SCOPES": {"read_profile": "Lees profielgegevens (gefilterd op consent)"},
    "DEFAULT_SCOPES": ["read_profile"],
    "PKCE_REQUIRED": True,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 3600,
    "AUTHORIZATION_CODE_EXPIRE_SECONDS": 300,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["http", "https"],
}
