import base64
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def _decode_payload(token: str) -> dict:
    _, payload, _ = token.split(".")
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def test_mint_test_token_for_registered_app(mock_wies):
    out = StringIO()
    call_command("mint_test_token", "--app=mock-wies", stdout=out)
    token = out.getvalue().strip()
    payload = _decode_payload(token)
    assert payload["azp"] == "mock-wies"
    assert "exp" in payload


def test_mint_test_token_fails_for_unknown_app(db):
    with pytest.raises(CommandError):
        call_command("mint_test_token", "--app=onbekend")
