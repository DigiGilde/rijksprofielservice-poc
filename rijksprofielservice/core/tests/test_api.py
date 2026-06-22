import json
from datetime import timedelta

import pytest
from django.utils import timezone
from oauth2_provider.models import AccessToken

pytestmark = pytest.mark.django_db


# -------------------------- happy paths --------------------------

def test_batch_returns_consented_profile(client, alice, mock_wies, alice_consents_wies, wies_token):
    response = client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": ["sub-alice"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    assert response.status_code == 200, response.content
    profile = response.json()["profiles"]["sub-alice"]
    assert profile["naam"] == "Alice Aap"
    assert profile["email"] == "alice@minbzk.nl"
    assert profile["telefoon"] == "06-1234"
    assert profile["functie"] == "Beleidsmedewerker"


def test_batch_filters_fields_to_requested_only(client, alice, mock_wies, alice_consents_wies, wies_token):
    """Mock Wies vraagt geen 'organisatie' — die mag niet in de response staan."""
    response = client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": ["sub-alice"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    profile = response.json()["profiles"]["sub-alice"]
    assert "organisatie" not in profile


def test_batch_filters_to_granted_fields_subset(client, alice, mock_wies, alice_consents_wies, wies_token):
    """Als de gebruiker maar een subset gegrant heeft, krijgt de app ook alleen die velden."""
    alice_consents_wies.granted_fields = ["naam", "email"]
    alice_consents_wies.save(update_fields=["granted_fields"])
    response = client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": ["sub-alice"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    profile = response.json()["profiles"]["sub-alice"]
    assert profile["naam"] == "Alice Aap"
    assert profile["email"] == "alice@minbzk.nl"
    assert "telefoon" not in profile
    assert "functie" not in profile


def test_batch_returns_null_for_user_without_consent(client, alice, mock_wies, wies_token):
    """Alice heeft geen consent gegeven aan mock-wies."""
    response = client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": ["sub-alice"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    assert response.json()["profiles"]["sub-alice"] is None


def test_batch_returns_null_for_unknown_subject(client, mock_wies, wies_token):
    response = client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": ["sub-onbekend"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    assert response.json()["profiles"]["sub-onbekend"] is None


def test_batch_mixed_subjects(client, alice, bob, mock_wies, alice_consents_wies, wies_token):
    response = client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": ["sub-alice", "sub-bob", "sub-x"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    profiles = response.json()["profiles"]
    assert profiles["sub-alice"] is not None
    assert profiles["sub-bob"] is None
    assert profiles["sub-x"] is None


def test_single_profile_endpoint(client, alice, mock_wies, alice_consents_wies, wies_token):
    response = client.get(
        "/api/v1/profiles/sub-alice",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    assert response.status_code == 200
    assert response.json()["naam"] == "Alice Aap"


# -------------------------- negative paths --------------------------

def test_single_profile_returns_403_without_consent(client, alice, mock_wies, wies_token):
    response = client.get(
        "/api/v1/profiles/sub-alice",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    assert response.status_code == 403


def test_single_profile_returns_404_for_unknown_subject(client, mock_wies, wies_token):
    response = client.get(
        "/api/v1/profiles/sub-onbekend",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    assert response.status_code == 404


def test_api_returns_401_without_token(client, mock_wies):
    response = client.get("/api/v1/profiles/sub-alice")
    assert response.status_code == 401


def test_api_returns_401_for_expired_token(client, alice, mock_wies, mock_wies_m2m_dot_app, alice_consents_wies):
    expired = AccessToken.objects.create(
        application=mock_wies_m2m_dot_app,
        token="expired-token",
        expires=timezone.now() - timedelta(seconds=60),
        scope="read_profile",
    )
    response = client.get(
        "/api/v1/profiles/sub-alice",
        HTTP_AUTHORIZATION=f"Bearer {expired.token}",
    )
    assert response.status_code == 401


def test_api_returns_403_for_unapproved_app(client, alice, mock_wies, alice_consents_wies, wies_token):
    """Niet-goedgekeurde app: token blijft geldig, maar business-laag weigert."""
    mock_wies.is_approved = False
    mock_wies.save()
    response = client.get(
        "/api/v1/profiles/sub-alice",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    assert response.status_code == 403


def test_api_returns_401_for_malformed_token(client, mock_wies):
    response = client.get(
        "/api/v1/profiles/sub-alice",
        HTTP_AUTHORIZATION="Bearer notatoken",
    )
    assert response.status_code == 401


def test_batch_rejects_non_list_subject_ids(client, mock_wies, wies_token):
    response = client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": "sub-alice"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    assert response.status_code == 400


def test_api_request_is_logged(client, alice, mock_wies, alice_consents_wies, wies_token):
    from rijksprofielservice.core.models import APIRequest

    client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": ["sub-alice", "sub-bob"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    log = APIRequest.objects.get()
    assert log.application == mock_wies
    assert log.subject_ids == ["sub-alice", "sub-bob"]


# -------------------------- user-bound token (Authorization Code) --------------------------


def test_me_endpoint_returns_profile_for_user_bound_token(client, alice, mock_wies, alice_consents_wies, mock_wies_dot_app):
    token = AccessToken.objects.create(
        user=alice,
        application=mock_wies_dot_app,
        token="alice-user-token",
        expires=timezone.now() + timedelta(hours=1),
        scope="read_profile",
    )
    response = client.get("/api/v1/profiles/me", HTTP_AUTHORIZATION=f"Bearer {token.token}")
    assert response.status_code == 200
    body = response.json()
    assert body["naam"] == "Alice Aap"
    assert "organisatie" not in body  # niet in requested_fields voor mock-wies


def test_me_endpoint_filters_by_granted_fields(client, alice, mock_wies, alice_consents_wies, mock_wies_dot_app):
    """Subset op Consent.granted_fields filtert ook /profiles/me."""
    alice_consents_wies.granted_fields = ["naam", "email"]
    alice_consents_wies.save(update_fields=["granted_fields"])
    token = AccessToken.objects.create(
        user=alice,
        application=mock_wies_dot_app,
        token="alice-user-token-subset",
        expires=timezone.now() + timedelta(hours=1),
        scope="read_profile",
    )
    response = client.get("/api/v1/profiles/me", HTTP_AUTHORIZATION=f"Bearer {token.token}")
    assert response.status_code == 200
    body = response.json()
    assert body["naam"] == "Alice Aap"
    assert "telefoon" not in body
    assert "functie" not in body


def test_me_endpoint_returns_403_without_consent(client, alice, mock_wies, mock_wies_dot_app):
    """Zonder actieve Consent geeft /profiles/me een 403, ook met geldig user-token."""
    token = AccessToken.objects.create(
        user=alice,
        application=mock_wies_dot_app,
        token="alice-user-token-no-consent",
        expires=timezone.now() + timedelta(hours=1),
        scope="read_profile",
    )
    response = client.get("/api/v1/profiles/me", HTTP_AUTHORIZATION=f"Bearer {token.token}")
    assert response.status_code == 403


def test_me_endpoint_rejects_client_credentials_token(client, mock_wies, wies_token):
    response = client.get("/api/v1/profiles/me", HTTP_AUTHORIZATION=f"Bearer {wies_token}")
    assert response.status_code == 403


def test_batch_endpoint_rejects_user_bound_token(client, alice, mock_wies, mock_wies_dot_app):
    token = AccessToken.objects.create(
        user=alice,
        application=mock_wies_dot_app,
        token="alice-user-token-2",
        expires=timezone.now() + timedelta(hours=1),
        scope="read_profile",
    )
    response = client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": ["sub-alice"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token.token}",
    )
    assert response.status_code == 403
