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
