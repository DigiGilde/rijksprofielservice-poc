"""Mint een mock JWT voor lokale API-tests.

PoC1: signature wordt niet geverifieerd door `ClientCredentialsJWTAuthentication`,
dus de signature mag een dummy zijn. Token bevat `azp` (client_id) en `exp`.
"""

import base64
import json
import time

from django.core.management.base import BaseCommand, CommandError

from rijksprofielservice.core.models import Application


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Command(BaseCommand):
    help = "Mint een mock JWT voor een geregistreerde Application (PoC1)."

    def add_arguments(self, parser):
        parser.add_argument("--app", required=True, help="client_id van de Application")
        parser.add_argument("--ttl", type=int, default=3600, help="Levensduur in seconden")

    def handle(self, *args, **options):
        client_id = options["app"]
        ttl = options["ttl"]

        if not Application.objects.filter(client_id=client_id).exists():
            msg = f"Onbekende client_id: {client_id}"
            raise CommandError(msg)

        header = {"alg": "none", "typ": "JWT"}
        payload = {
            "azp": client_id,
            "iss": "mock-issuer",
            "exp": int(time.time()) + ttl,
        }
        token = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}.mock"
        self.stdout.write(token)
