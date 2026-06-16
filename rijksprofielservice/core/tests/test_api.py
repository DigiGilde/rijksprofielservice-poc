import json

import pytest

pytestmark = pytest.mark.django_db


# -------------------------- happy paths --------------------------

def test_batch_returns_consented_profile(client, alice, mock_wies, alice_consents_wies, wies_token):
    response = client.post(
        "/api/v1/profiles/batch",
        data=json.dumps({"subject_ids": ["sub-alice"]}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {wies_token}",
    )
    assert response.status_code == 200
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


def test_api_returns_401_for_expired_token(client, alice, mock_wies, alice_consents_wies, mint_token):
    expired = mint_token(exp_offset=-60)
    response = client.get(
        "/api/v1/profiles/sub-alice",
        HTTP_AUTHORIZATION=f"Bearer {expired}",
    )
    assert response.status_code == 401


def test_api_returns_401_for_unapproved_app(client, alice, mock_wies, alice_consents_wies, mint_token):
    mock_wies.is_approved = False
    mock_wies.save()
    token = mint_token(client_id="mock-wies")
    response = client.get(
        "/api/v1/profiles/sub-alice",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 401


def test_api_returns_401_for_unknown_client(client, alice, mock_wies, alice_consents_wies, mint_token):
    token = mint_token(client_id="onbekend")
    response = client.get(
        "/api/v1/profiles/sub-alice",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 401


def test_api_returns_401_for_malformed_token(client, mock_wies):
    response = client.get(
        "/api/v1/profiles/sub-alice",
        HTTP_AUTHORIZATION="Bearer notajwt",
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
