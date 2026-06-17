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


def _make_dot_app(*, client_id, name, grant_type, redirect_uris=""):
    from oauth2_provider.models import Application as DotApplication

    return DotApplication.objects.create(
        client_id=client_id,
        name=name,
        client_type="confidential",
        authorization_grant_type=grant_type,
        client_secret=f"secret-{client_id}",
        redirect_uris=redirect_uris,
        skip_authorization=(grant_type == "client-credentials"),
        algorithm="",
        hash_client_secret=False,
    )


@pytest.fixture
def mock_wies_dot_app(db):
    return _make_dot_app(
        client_id="mock-wies",
        name="Mock Wies",
        grant_type="authorization-code",
        redirect_uris="http://testserver/demo/mock-wies-landing/",
    )


@pytest.fixture
def mock_wies_m2m_dot_app(db):
    return _make_dot_app(client_id="mock-wies-m2m", name="Mock Wies (M2M)", grant_type="client-credentials")


@pytest.fixture
def mock_wies(mock_wies_dot_app):
    return Application.objects.create(
        naam="Mock Wies",
        client_id="mock-wies",
        beschrijving="Bemiddelingsplatform.",
        requested_fields=["naam", "email", "telefoon", "functie", "avatar"],
        is_approved=True,
        oauth_app=mock_wies_dot_app,
    )


@pytest.fixture
def mock_amt_dot_app(db):
    return _make_dot_app(
        client_id="mock-amt",
        name="Mock AMT",
        grant_type="authorization-code",
        redirect_uris="http://testserver/demo/mock-amt-landing/",
    )


@pytest.fixture
def mock_amt(mock_amt_dot_app):
    return Application.objects.create(
        naam="Mock AMT",
        client_id="mock-amt",
        beschrijving="Account Management Tool.",
        requested_fields=["naam", "email", "avatar"],
        is_approved=True,
        oauth_app=mock_amt_dot_app,
    )


@pytest.fixture
def alice_consents_wies(alice, mock_wies):
    return Consent.objects.create(user=alice, application=mock_wies)


@pytest.fixture
def wies_token(mock_wies, mock_wies_m2m_dot_app):
    """Geldig client-credentials AccessToken voor `mock-wies-m2m`."""
    from datetime import timedelta

    from django.utils import timezone
    from oauth2_provider.models import AccessToken

    tok = AccessToken.objects.create(
        application=mock_wies_m2m_dot_app,
        token="testtoken-wies-m2m",
        expires=timezone.now() + timedelta(hours=1),
        scope="read_profile",
    )
    return tok.token
