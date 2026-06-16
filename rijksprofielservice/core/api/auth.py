"""JWT-authenticatie voor consuming apps (client-credentials grant).

PoC2: stateless RS256-validatie tegen de profielservice Keycloak realm.
- JWKS opgehaald van issuer/protocol/openid-connect/certs, gecached 5 min.
- Refresh-on-unknown-kid voor key rotation (1× retry).
- Strikte iss-check tegen settings.PROFIELSERVICE_JWT_ISSUER.
- Algoritme-whitelist: RS256.
- azp claim moet matchen met een goedgekeurde Application.

Dev-bypass: als settings.PROFIELSERVICE_JWT_ALLOW_TEST_KEY=true en het token
heeft kid="test-kid", dan wordt de lokale test-public-key gebruikt. Bedoeld
voor mock-landing demo en mint_test_token zonder Keycloak-roundtrip.
"""

import base64
import json
import logging
import time
import urllib.request

from authlib.jose import JsonWebKey, JsonWebToken
from authlib.jose.errors import JoseError
from django.conf import settings
from rest_framework import authentication, exceptions

from rijksprofielservice.core.models import Application

logger = logging.getLogger(__name__)

ALLOWED_ALGORITHMS = ["RS256"]
TEST_KID = "test-kid"
JWKS_CACHE_TTL_SECONDS = 300

# Module-level cache: {issuer: (fetched_at_epoch, {kid: JsonWebKey})}
_jwks_cache: dict[str, tuple[float, dict]] = {}


class ConsumingApp:
    """Pseudo-user voor consuming apps. DRF verwacht een user-object."""

    def __init__(self, application: Application):
        self.application = application
        self.is_authenticated = True
        self.is_active = True

    def __str__(self):
        return f"app:{self.application.client_id}"


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def _decode_header(token: str) -> dict:
    try:
        header_b64 = token.split(".", 1)[0]
        return json.loads(_b64url_decode(header_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        msg = "Malformed JWT header"
        raise exceptions.AuthenticationFailed(msg) from exc


def _decode_payload_unsafe(token: str) -> dict:
    """Decode payload zonder signature-check — alleen voor iss-pre-check."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("not three parts")
        return json.loads(_b64url_decode(parts[1]))
    except (ValueError, json.JSONDecodeError) as exc:
        msg = "Malformed JWT payload"
        raise exceptions.AuthenticationFailed(msg) from exc


def _fetch_jwks(issuer: str) -> dict:
    """Haal JWKS op bij issuer/protocol/openid-connect/certs en parse keys per kid."""
    url = f"{issuer.rstrip('/')}/protocol/openid-connect/certs"
    logger.info("Fetching JWKS from %s", url)
    with urllib.request.urlopen(url, timeout=5) as response:
        raw = json.load(response)
    keys_by_kid: dict[str, JsonWebKey] = {}
    for jwk_dict in raw.get("keys", []):
        kid = jwk_dict.get("kid")
        if not kid:
            continue
        keys_by_kid[kid] = JsonWebKey.import_key(jwk_dict)
    return keys_by_kid


def _load_test_public_key() -> JsonWebKey:
    """Laad het lokale test-keypair (dev-bypass)."""
    with settings.PROFIELSERVICE_JWT_TEST_PUBLIC_KEY_PATH.open("rb") as f:
        return JsonWebKey.import_key(f.read())


def _get_key_for_kid(issuer: str, kid: str, *, allow_refresh: bool = True) -> JsonWebKey:
    """Vind de publieke key voor `kid`. Cache 5 min; refresh-on-unknown-kid."""
    if settings.PROFIELSERVICE_JWT_ALLOW_TEST_KEY and kid == TEST_KID:
        return _load_test_public_key()

    now = time.time()
    cached = _jwks_cache.get(issuer)
    if cached and (now - cached[0]) < JWKS_CACHE_TTL_SECONDS:
        keys = cached[1]
        if kid in keys:
            return keys[kid]
        # Cache vers maar kid onbekend → mogelijk key rotation. Refresh 1×.
        if not allow_refresh:
            msg = f"Onbekende kid: {kid}"
            raise exceptions.AuthenticationFailed(msg)
    else:
        keys = None

    # Refresh JWKS.
    try:
        keys = _fetch_jwks(issuer)
    except (OSError, ValueError) as exc:
        logger.warning("JWKS fetch failed for %s: %s", issuer, exc)
        msg = "Kan JWKS niet ophalen"
        raise exceptions.AuthenticationFailed(msg) from exc
    _jwks_cache[issuer] = (now, keys)
    if kid not in keys:
        msg = f"Onbekende kid: {kid}"
        raise exceptions.AuthenticationFailed(msg)
    return keys[kid]


def _clear_cache():
    """Voor tests: wis JWKS-cache."""
    _jwks_cache.clear()


class ClientCredentialsJWTAuthentication(authentication.BaseAuthentication):
    """Authenticeert via Bearer JWT van profielservice-realm (RS256 + JWKS)."""

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None
        token = auth_header.removeprefix(f"{self.keyword} ").strip()

        header = _decode_header(token)
        alg = header.get("alg")
        kid = header.get("kid")
        if alg not in ALLOWED_ALGORITHMS:
            msg = f"Algoritme niet toegestaan: {alg!r}"
            raise exceptions.AuthenticationFailed(msg)
        if not kid:
            msg = "Token mist kid"
            raise exceptions.AuthenticationFailed(msg)

        # iss-check vóór signature: voorkomt onnodige JWKS-calls bij verkeerde issuer.
        payload_unsafe = _decode_payload_unsafe(token)
        expected_iss = settings.PROFIELSERVICE_JWT_ISSUER
        if not expected_iss:
            msg = "PROFIELSERVICE_JWT_ISSUER is niet geconfigureerd"
            raise exceptions.AuthenticationFailed(msg)
        if payload_unsafe.get("iss") != expected_iss:
            msg = "Issuer komt niet overeen"
            raise exceptions.AuthenticationFailed(msg)

        key = _get_key_for_kid(expected_iss, kid)

        try:
            claims = JsonWebToken(ALLOWED_ALGORITHMS).decode(token, key)
            # Authlib's claims.validate() checkt exp/nbf/iat als ze aanwezig zijn.
            claims.validate(now=int(time.time()), leeway=0)
        except JoseError as exc:
            logger.info("JWT validation failed: %s", exc)
            msg = f"JWT-validatie mislukt: {exc}"
            raise exceptions.AuthenticationFailed(msg) from exc

        client_id = claims.get("azp") or claims.get("client_id")
        if not client_id:
            msg = "Token mist azp/client_id"
            raise exceptions.AuthenticationFailed(msg)

        app = Application.objects.filter(client_id=client_id).first()
        if app is None:
            msg = "Onbekende client"
            raise exceptions.AuthenticationFailed(msg)
        if not app.is_approved:
            msg = "App niet goedgekeurd"
            raise exceptions.AuthenticationFailed(msg)

        return (ConsumingApp(app), token)

    def authenticate_header(self, request):
        return self.keyword
