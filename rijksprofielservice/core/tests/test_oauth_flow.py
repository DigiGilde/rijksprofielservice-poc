"""Tests voor de OAuth Authorization Code flow tegen de profielservice OAuth-server."""

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import pytest
from oauth2_provider.models import AccessToken, Grant

from rijksprofielservice.core.models import Consent

pytestmark = pytest.mark.django_db


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


@pytest.fixture
def authorize_params(mock_wies):
    verifier, challenge = _pkce_pair()
    redirect_uri = "http://testserver/demo/mock-wies-landing/"
    return {
        "response_type": "code",
        "client_id": mock_wies.client_id,
        "redirect_uri": redirect_uri,
        "scope": "read_profile",
        "state": "xyz123",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "_verifier": verifier,
    }


def _authorize_qs(params):
    return "&".join(f"{k}={v}" for k, v in params.items() if not k.startswith("_"))


def test_authorize_requires_login(client, authorize_params):
    response = client.get(f"/o/authorize/?{_authorize_qs(authorize_params)}")
    assert response.status_code == 302
    assert "/inloggen/" in response.url


def test_authorize_renders_custom_consent_template(client, alice, mock_wies, authorize_params):
    client.force_login(alice)
    response = client.get(f"/o/authorize/?{_authorize_qs(authorize_params)}")
    assert response.status_code == 200
    assert b"Mock Wies" in response.content
    assert b"telefoon" in response.content


def test_grant_creates_authorization_code(client, alice, mock_wies, authorize_params):
    client.force_login(alice)
    grant_post = {k: v for k, v in authorize_params.items() if not k.startswith("_")}
    grant_post["allow"] = "Authorize"
    response = client.post("/o/authorize/", grant_post)
    assert response.status_code == 302
    qs = parse_qs(urlparse(response.url).query)
    assert "code" in qs
    assert qs["state"] == ["xyz123"]
    assert Grant.objects.filter(user=alice, application=mock_wies.oauth_app).exists()


def _complete_flow(client, alice, mock_wies, authorize_params):
    """Helper: doorloop authorize + token exchange, return access_token-body."""
    client.force_login(alice)
    grant_post = {k: v for k, v in authorize_params.items() if not k.startswith("_")}
    grant_post["allow"] = "Authorize"
    grant_response = client.post("/o/authorize/", grant_post)
    code = parse_qs(urlparse(grant_response.url).query)["code"][0]
    token_response = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": authorize_params["redirect_uri"],
            "client_id": mock_wies.client_id,
            "client_secret": mock_wies.oauth_app.client_secret,
            "code_verifier": authorize_params["_verifier"],
        },
    )
    return token_response


def test_token_exchange_creates_consent_via_signal(client, alice, mock_wies, authorize_params):
    """app_authorized signal vuurt op /o/token/-call; daar wordt Consent aangemaakt."""
    response = _complete_flow(client, alice, mock_wies, authorize_params)
    assert response.status_code == 200
    assert Consent.objects.filter(user=alice, application=mock_wies, revoked_at__isnull=True).exists()


def test_deny_does_not_create_consent(client, alice, mock_wies, authorize_params):
    client.force_login(alice)
    deny_post = {k: v for k, v in authorize_params.items() if not k.startswith("_")}
    # Geen `allow` field → DOT interpreteert als access_denied
    response = client.post("/o/authorize/", deny_post)
    assert response.status_code == 302
    qs = parse_qs(urlparse(response.url).query)
    assert qs.get("error") == ["access_denied"]
    assert not Consent.objects.filter(user=alice, application=mock_wies, revoked_at__isnull=True).exists()
    assert not Grant.objects.filter(user=alice, application=mock_wies.oauth_app).exists()


def test_token_exchange_returns_access_token(client, alice, mock_wies, authorize_params):
    client.force_login(alice)
    grant_post = {k: v for k, v in authorize_params.items() if not k.startswith("_")}
    grant_post["allow"] = "Authorize"
    grant_response = client.post("/o/authorize/", grant_post)
    code = parse_qs(urlparse(grant_response.url).query)["code"][0]

    response = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": authorize_params["redirect_uri"],
            "client_id": mock_wies.client_id,
            "client_secret": mock_wies.oauth_app.client_secret,
            "code_verifier": authorize_params["_verifier"],
        },
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert "access_token" in body
    assert AccessToken.objects.filter(token=body["access_token"], user=alice).exists()


def test_regrant_after_revoke_creates_new_consent_row(client, alice, mock_wies, authorize_params):
    from django.utils import timezone

    _complete_flow(client, alice, mock_wies, authorize_params)
    assert Consent.objects.filter(user=alice, application=mock_wies, revoked_at__isnull=True).exists()

    Consent.objects.filter(user=alice, application=mock_wies).update(revoked_at=timezone.now())

    verifier2, challenge2 = _pkce_pair()
    params2 = dict(authorize_params)
    params2["state"] = "second"
    params2["code_challenge"] = challenge2
    params2["_verifier"] = verifier2
    _complete_flow(client, alice, mock_wies, params2)

    consents = Consent.objects.filter(user=alice, application=mock_wies).order_by("granted_at")
    assert consents.count() == 2
    assert consents.first().revoked_at is not None
    assert consents.last().revoked_at is None
