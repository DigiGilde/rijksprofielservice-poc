"""Mint een RS256 JWT met het lokale test-keypair.

Bruikbaar wanneer settings.PROFIELSERVICE_JWT_ALLOW_TEST_KEY=true:
de auth-laag accepteert dan tokens met kid="test-kid", geverifieerd
tegen config/test_keys/jwt_test_pub.pem.

Bedoeld voor mock-landing demo en lokale tests zonder Keycloak-roundtrip.
"""

import time

from authlib.jose import JsonWebKey, JsonWebToken
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from rijksprofielservice.core.api.auth import TEST_KID
from rijksprofielservice.core.models import Application


class Command(BaseCommand):
    help = "Mint een RS256 JWT voor een geregistreerde Application (lokaal test-keypair)."

    def add_arguments(self, parser):
        parser.add_argument("--app", required=True, help="client_id van de Application")
        parser.add_argument("--ttl", type=int, default=3600, help="Levensduur in seconden")

    def handle(self, *args, **options):
        client_id = options["app"]
        ttl = options["ttl"]

        if not Application.objects.filter(client_id=client_id).exists():
            msg = f"Onbekende client_id: {client_id}"
            raise CommandError(msg)

        if not settings.PROFIELSERVICE_JWT_ISSUER:
            msg = "PROFIELSERVICE_JWT_ISSUER is niet geconfigureerd"
            raise CommandError(msg)
        if not settings.PROFIELSERVICE_JWT_TEST_PRIVATE_KEY_PATH.exists():
            msg = f"Private test key niet gevonden: {settings.PROFIELSERVICE_JWT_TEST_PRIVATE_KEY_PATH}"
            raise CommandError(msg)

        with settings.PROFIELSERVICE_JWT_TEST_PRIVATE_KEY_PATH.open("rb") as f:
            private_key = JsonWebKey.import_key(f.read())

        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT", "kid": TEST_KID}
        payload = {
            "iss": settings.PROFIELSERVICE_JWT_ISSUER,
            "azp": client_id,
            "client_id": client_id,
            "iat": now,
            "exp": now + ttl,
        }
        token_bytes = JsonWebToken(["RS256"]).encode(header, payload, private_key)
        self.stdout.write(token_bytes.decode())
