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


def test_authenticate_returns_none_for_unknown_user_and_logs_event():
    backend = AuthBackend()
    result = backend.authenticate(request=None, username="sub-x", email="unknown@minbzk.nl")
    assert result is None
    assert AuthEvent.objects.filter(name="Login.fail", user_email="unknown@minbzk.nl").exists()


def test_authenticate_is_case_insensitive_on_email():
    User.objects.create_user(email="Eve@minbzk.nl", first_name="Eve", last_name="Eend")
    backend = AuthBackend()
    user = backend.authenticate(request=None, username="sub-eve", email="eve@MINBZK.nl")
    assert user is not None
