"""Tests voor de OAuth-style consent flow (PoC1 light mimick)."""

from urllib.parse import parse_qs, urlparse

import pytest

from rijksprofielservice.core.models import Consent

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_wies_with_redirect(mock_wies):
    mock_wies.redirect_uris = ["http://localhost:8000/demo/mock-wies-landing/"]
    mock_wies.save(update_fields=["redirect_uris"])
    return mock_wies


@pytest.fixture
def authorize_url(mock_wies_with_redirect):
    return (
        "/oauth/authorize"
        f"?client_id={mock_wies_with_redirect.client_id}"
        f"&redirect_uri={mock_wies_with_redirect.redirect_uris[0]}"
        "&state=xyz123"
    )


def test_authorize_requires_login(client, authorize_url):
    response = client.get(authorize_url)
    assert response.status_code == 302
    assert "/inloggen/" in response.url


def test_authorize_unknown_client_returns_400(client, alice):
    client.force_login(alice)
    response = client.get("/oauth/authorize?client_id=fake&redirect_uri=http://x/&state=s")
    assert response.status_code == 400
    assert b"Onbekende client" in response.content


def test_authorize_invalid_redirect_uri_returns_400(client, alice, mock_wies_with_redirect):
    client.force_login(alice)
    response = client.get(
        f"/oauth/authorize?client_id={mock_wies_with_redirect.client_id}&redirect_uri=http://evil.example/&state=s"
    )
    assert response.status_code == 400
    assert b"Ongeldige redirect_uri" in response.content


def test_authorize_not_approved_returns_403(client, alice, mock_wies_with_redirect):
    mock_wies_with_redirect.is_approved = False
    mock_wies_with_redirect.save(update_fields=["is_approved"])
    client.force_login(alice)
    response = client.get(
        f"/oauth/authorize?client_id={mock_wies_with_redirect.client_id}"
        f"&redirect_uri={mock_wies_with_redirect.redirect_uris[0]}&state=s"
    )
    assert response.status_code == 403


def test_authorize_invalid_requested_fields_returns_400(client, alice, authorize_url):
    client.force_login(alice)
    response = client.get(authorize_url + "&requested_fields=passport_number")
    assert response.status_code == 400
    assert b"Ongeldige requested_fields" in response.content


def test_authorize_stores_params_in_session_and_redirects(client, alice, authorize_url):
    client.force_login(alice)
    response = client.get(authorize_url)
    assert response.status_code == 302
    assert response.url == "/oauth/consent"
    session_params = client.session["oauth_authorize_params"]
    assert session_params["client_id"] == "mock-wies"
    assert session_params["state"] == "xyz123"
    assert "naam" in session_params["effective_fields"]


def test_consent_screen_without_session_returns_400(client, alice):
    client.force_login(alice)
    response = client.get("/oauth/consent")
    assert response.status_code == 400


def test_consent_screen_renders_app_and_fields(client, alice, authorize_url):
    client.force_login(alice)
    client.get(authorize_url)
    response = client.get("/oauth/consent")
    assert response.status_code == 200
    assert b"Mock Wies" in response.content
    assert b"telefoon" in response.content


def test_consent_grant_creates_consent_and_redirects_with_state(client, alice, authorize_url, mock_wies_with_redirect):
    client.force_login(alice)
    client.get(authorize_url)
    response = client.post("/oauth/consent/decide", {"decision": "grant"})
    assert response.status_code == 302
    parsed = urlparse(response.url)
    qs = parse_qs(parsed.query)
    assert qs["consent"] == ["granted"]
    assert qs["state"] == ["xyz123"]
    assert qs["subject_id"] == ["sub-alice"]  # alice fixture zet sso_subject="sub-alice"
    assert parsed.path == "/demo/mock-wies-landing/"
    assert Consent.objects.filter(user=alice, application=mock_wies_with_redirect, revoked_at__isnull=True).exists()


def test_consent_deny_does_not_create_consent(client, alice, authorize_url, mock_wies_with_redirect):
    client.force_login(alice)
    client.get(authorize_url)
    response = client.post("/oauth/consent/decide", {"decision": "deny"})
    assert response.status_code == 302
    qs = parse_qs(urlparse(response.url).query)
    assert qs["consent"] == ["denied"]
    assert qs["state"] == ["xyz123"]
    assert "subject_id" not in qs  # geen consent → geen id-lek
    assert not Consent.objects.filter(user=alice, application=mock_wies_with_redirect, revoked_at__isnull=True).exists()


def test_regrant_after_revoke_creates_new_consent_row(client, alice, authorize_url, mock_wies_with_redirect):
    from django.utils import timezone

    # Eerste grant
    client.force_login(alice)
    client.get(authorize_url)
    client.post("/oauth/consent/decide", {"decision": "grant"})

    # Soft-revoke (zoals consent_revoke view doet)
    Consent.objects.filter(user=alice, application=mock_wies_with_redirect).update(revoked_at=timezone.now())

    # Re-grant
    client.get(authorize_url)
    client.post("/oauth/consent/decide", {"decision": "grant"})

    consents = Consent.objects.filter(user=alice, application=mock_wies_with_redirect).order_by("granted_at")
    assert consents.count() == 2
    assert consents.first().revoked_at is not None  # oude blijft revoked
    assert consents.last().revoked_at is None  # nieuwe is actief


def test_consent_decide_without_session_returns_400(client, alice):
    client.force_login(alice)
    response = client.post("/oauth/consent/decide", {"decision": "grant"})
    assert response.status_code == 400
