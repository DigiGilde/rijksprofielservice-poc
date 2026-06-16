import pytest
from django.contrib.auth import get_user_model

from rijksprofielservice.rijksauth.auth_backend import AuthBackend
from rijksprofielservice.rijksauth.models import AuthEvent

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_authenticate_returns_existing_user():
    User.objects.create_user(email="dora@minbzk.nl", first_name="Dora", last_name="Das")
    backend = AuthBackend()
    user = backend.authenticate(request=None, username="sub-dora", email="dora@minbzk.nl")
    assert user is not None
    assert user.email == "dora@minbzk.nl"


def test_authenticate_auto_provisions_unknown_user_and_logs_event():
    backend = AuthBackend()
    result = backend.authenticate(
        request=None,
        username="sub-x",
        email="unknown@minbzk.nl",
        first_name="Unknown",
        last_name="User",
    )
    assert result is not None
    assert result.email == "unknown@minbzk.nl"
    assert result.first_name == "Unknown"
    assert result.last_name == "User"
    assert AuthEvent.objects.filter(name="Login.provisioned", user_email="unknown@minbzk.nl").exists()


def test_authenticate_returns_none_when_username_or_email_missing():
    backend = AuthBackend()
    assert backend.authenticate(request=None, username="", email="x@y.nl") is None
    assert backend.authenticate(request=None, username="sub", email="") is None


def test_authenticate_is_case_insensitive_on_email():
    User.objects.create_user(email="Eve@minbzk.nl", first_name="Eve", last_name="Eend")
    backend = AuthBackend()
    user = backend.authenticate(request=None, username="sub-eve", email="eve@MINBZK.nl")
    assert user is not None
