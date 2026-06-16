import pytest
from django.contrib.auth import get_user_model

from rijksprofielservice.core.models import Application, Consent, UserProfile

User = get_user_model()


@pytest.fixture
def alice(db):
    user = User.objects.create_user(
        email="alice@minbzk.nl",
        first_name="Alice",
        last_name="Aap",
    )
    # Signal maakt het profiel aan; we updaten alleen de velden.
    UserProfile.objects.filter(user=user).update(
        sso_subject="sub-alice",
        telefoon="06-1234",
        functie="Beleidsmedewerker",
        organisatie="BZK",
    )
    return user


@pytest.fixture
def bob(db):
    user = User.objects.create_user(
        email="bob@minbzk.nl",
        first_name="Bob",
        last_name="Beer",
    )
    UserProfile.objects.filter(user=user).update(
        sso_subject="sub-bob",
        telefoon="06-5678",
        functie="Adviseur",
        organisatie="BZK",
    )
    return user


@pytest.fixture
def mock_wies(db):
    return Application.objects.create(
        naam="Mock Wies",
        client_id="mock-wies",
        beschrijving="Bemiddelingsplatform.",
        requested_fields=["naam", "email", "telefoon", "functie", "avatar"],
        is_approved=True,
    )


@pytest.fixture
def mock_amt(db):
    return Application.objects.create(
        naam="Mock AMT",
        client_id="mock-amt",
        beschrijving="Account Management Tool.",
        requested_fields=["naam", "email", "avatar"],
        is_approved=True,
    )


@pytest.fixture
def alice_consents_wies(alice, mock_wies):
    return Consent.objects.create(user=alice, application=mock_wies)


@pytest.fixture
def wies_token(mock_wies):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("mint_test_token", "--app=mock-wies", stdout=out)
    return out.getvalue().strip()


@pytest.fixture(autouse=True)
def _clear_jwks_cache():
    """Voorkom dat tests elkaars JWKS-cache zien."""
    from rijksprofielservice.core.api.auth import _clear_cache

    _clear_cache()
    yield
    _clear_cache()


@pytest.fixture
def mint_token():
    """Helper: mint een RS256 token met de test-keypair.

    Parameters laten testen toe om kid/alg/iss/azp/exp af te wijken voor negatieve checks.
    """
    import time

    from authlib.jose import JsonWebKey, JsonWebToken
    from django.conf import settings

    def _mint(*, client_id="mock-wies", iss=None, exp_offset=3600, kid="test-kid", alg="RS256"):
        with settings.PROFIELSERVICE_JWT_TEST_PRIVATE_KEY_PATH.open("rb") as f:
            private_key = JsonWebKey.import_key(f.read())
        now = int(time.time())
        header = {"alg": alg, "typ": "JWT", "kid": kid}
        payload = {
            "iss": iss if iss is not None else settings.PROFIELSERVICE_JWT_ISSUER,
            "azp": client_id,
            "client_id": client_id,
            "iat": now,
            "exp": now + exp_offset,
        }
        return JsonWebToken([alg]).encode(header, payload, private_key).decode()

    return _mint
