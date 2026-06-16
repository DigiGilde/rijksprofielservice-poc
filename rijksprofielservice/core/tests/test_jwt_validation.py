"""Tests voor productie-grade JWT-validatie in core/api/auth.py.

Dekt: algoritme-whitelist, iss-strict, kid-required, signature-mismatch,
expired tokens, JWKS-cache TTL en refresh-on-unknown-kid.
"""

import base64
import json
import time
from unittest.mock import patch

import pytest
from authlib.jose import JsonWebKey, JsonWebToken

pytestmark = pytest.mark.django_db


# -------------------------- helpers --------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_alg_none_token(client_id="mock-wies"):
    """Mint een onveilig alg:none token (mag NIET geaccepteerd worden)."""
    header = {"alg": "none", "typ": "JWT", "kid": "test-kid"}
    payload = {
        "iss": "https://test-issuer.example/realms/profielservice",
        "azp": client_id,
        "exp": int(time.time()) + 3600,
    }
    return f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}."


def _make_token_with_alg(alg, client_id="mock-wies"):
    """Mint een token met een specifiek algoritme; signed met HS256 mag falen op alg-whitelist."""
    header = {"alg": alg, "typ": "JWT", "kid": "test-kid"}
    payload = {
        "iss": "https://test-issuer.example/realms/profielservice",
        "azp": client_id,
        "exp": int(time.time()) + 3600,
    }
    return f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}.signature"


# -------------------------- happy path --------------------------


def test_valid_rs256_token_authenticates(client, alice, mock_wies, alice_consents_wies, mint_token):
    token = mint_token()
    response = client.get("/api/v1/profiles/sub-alice", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200


# -------------------------- algoritme-whitelist --------------------------


def test_alg_none_is_rejected(client, mock_wies):
    token = _make_alg_none_token()
    response = client.get("/api/v1/profiles/sub-x", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401


def test_alg_hs256_is_rejected(client, mock_wies):
    token = _make_token_with_alg("HS256")
    response = client.get("/api/v1/profiles/sub-x", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401


# -------------------------- header validation --------------------------


def test_token_without_kid_is_rejected(client, mock_wies):
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": "https://test-issuer.example/realms/profielservice",
        "azp": "mock-wies",
        "exp": int(time.time()) + 3600,
    }
    token = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}.sig"
    response = client.get("/api/v1/profiles/sub-x", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401


# -------------------------- iss-check --------------------------


def test_token_with_wrong_iss_is_rejected(client, mock_wies, mint_token):
    token = mint_token(iss="https://malicious.example/realm")
    response = client.get("/api/v1/profiles/sub-x", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401


# -------------------------- signature --------------------------


def test_token_signed_with_other_key_is_rejected(client, mock_wies, settings):
    """Token met de juiste kid maar gesigned met andere RSA-key → 401."""
    # Genereer een vreemde key en sign daarmee.
    other_key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    header = {"alg": "RS256", "typ": "JWT", "kid": "test-kid"}  # claimt test-kid
    payload = {"iss": settings.PROFIELSERVICE_JWT_ISSUER, "azp": "mock-wies", "exp": int(time.time()) + 3600}
    token = JsonWebToken(["RS256"]).encode(header, payload, other_key).decode()
    response = client.get("/api/v1/profiles/sub-x", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401


# -------------------------- JWKS-cache --------------------------


def test_jwks_cache_refresh_on_unknown_kid(client, alice, mock_wies, alice_consents_wies, settings):
    """Cache zit vol met kid-A; token met kid-B komt binnen → 1x refresh-fetch → token slaagt."""
    from rijksprofielservice.core.api import auth as auth_module

    settings.PROFIELSERVICE_JWT_ALLOW_TEST_KEY = False  # forceer JWKS-pad

    # Genereer kid-A en kid-B keys.
    key_a_priv = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    key_a_pub = JsonWebKey.import_key(key_a_priv.as_dict(is_private=False))
    key_b_priv = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    key_b_pub = JsonWebKey.import_key(key_b_priv.as_dict(is_private=False))

    # Vul cache vooraf met kid-A (verse fetched_at) — simuleert "cache nog warm".
    issuer = settings.PROFIELSERVICE_JWT_ISSUER
    auth_module._jwks_cache[issuer] = (time.time(), {"kid-A": key_a_pub})

    # Token gemund met kid-B (key rotation scenario).
    header = {"alg": "RS256", "typ": "JWT", "kid": "kid-B"}
    payload = {
        "iss": issuer,
        "azp": "mock-wies",
        "exp": int(time.time()) + 3600,
    }
    token = JsonWebToken(["RS256"]).encode(header, payload, key_b_priv).decode()

    # Refresh-fetch levert nu beide keys.
    with patch.object(auth_module, "_fetch_jwks", return_value={"kid-A": key_a_pub, "kid-B": key_b_pub}) as fake_fetch:
        response = client.get("/api/v1/profiles/sub-alice", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    assert fake_fetch.call_count == 1  # exactly 1 refresh


def test_jwks_cache_ttl_expires(client, mock_wies, settings):
    """Na 5 min TTL wordt JWKS opnieuw gefetched."""
    from rijksprofielservice.core.api import auth as auth_module

    settings.PROFIELSERVICE_JWT_ALLOW_TEST_KEY = False

    # Plant een verse cache-entry met TTL die net niet verlopen is.
    issuer = settings.PROFIELSERVICE_JWT_ISSUER
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    pub = JsonWebKey.import_key(key.as_dict(is_private=False))
    auth_module._jwks_cache[issuer] = (time.time() - 100, {"kid-X": pub})

    # Token met kid-X — moet uit cache komen (geen fetch).
    header = {"alg": "RS256", "typ": "JWT", "kid": "kid-X"}
    payload = {"iss": issuer, "azp": "mock-wies", "exp": int(time.time()) + 3600}
    token = JsonWebToken(["RS256"]).encode(header, payload, key).decode()

    with patch.object(auth_module, "_fetch_jwks") as fake_fetch:
        client.get("/api/v1/profiles/sub-x", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert fake_fetch.call_count == 0  # binnen TTL → geen fetch

    # Force TTL-expiry door cache-entry op een oud timestamp te zetten.
    auth_module._jwks_cache[issuer] = (time.time() - 1000, {"kid-X": pub})
    with patch.object(auth_module, "_fetch_jwks", return_value={"kid-X": pub}) as fake_fetch:
        client.get("/api/v1/profiles/sub-x", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert fake_fetch.call_count == 1  # TTL verlopen → fetch
