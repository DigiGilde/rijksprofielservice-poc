"""JWT-authenticatie voor consuming apps (client-credentials grant).

PoC1: basis-validatie (decode, exp, azp → Application lookup).
PoC2: stateless JWKS-cached signature-verificatie, strikte iss-check.

Voor PoC1 verwachten we een ongetekende JWT-look-alike (header.payload.signature
met lege/dummy signature) of een HS256-token met een gedeeld secret — afhankelijk
van of er een echte Keycloak beschikbaar is. We doen hier alleen de claim-checks.
"""

import base64
import json
import logging
import time

from rest_framework import authentication, exceptions

from rijksprofielservice.core.models import Application

logger = logging.getLogger(__name__)


class ConsumingApp:
    """Pseudo-user voor consuming apps. DRF verwacht een user-object."""

    def __init__(self, application: Application):
        self.application = application
        self.is_authenticated = True
        self.is_active = True

    def __str__(self):
        return f"app:{self.application.client_id}"


def _decode_payload(token: str) -> dict:
    try:
        _header, payload, _sig = token.split(".")
    except ValueError as exc:
        msg = "Malformed JWT"
        raise exceptions.AuthenticationFailed(msg) from exc
    padded = payload + "=" * (-len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError) as exc:
        msg = "Cannot decode JWT payload"
        raise exceptions.AuthenticationFailed(msg) from exc


class ClientCredentialsJWTAuthentication(authentication.BaseAuthentication):
    """Authenticeert via Bearer JWT van profielservice-realm.

    Validaties (PoC1, minimaal):
      - claim `exp` (verlopen?)
      - claim `azp` (of `client_id`) matcht een Application met is_approved=True

    Nog niet (komt in PoC2):
      - Signature-verificatie tegen JWKS van de realm
      - Strikte `iss`-check
    """

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None
        token = auth_header.removeprefix(f"{self.keyword} ").strip()
        payload = _decode_payload(token)

        exp = payload.get("exp")
        if exp is not None and int(exp) < int(time.time()):
            msg = "Token expired"
            raise exceptions.AuthenticationFailed(msg)

        client_id = payload.get("azp") or payload.get("client_id")
        if not client_id:
            msg = "Token missing azp/client_id"
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
