import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db import IntegrityError, transaction
from django.utils import timezone

from rijksprofielservice.core.models import Consent, UserProfile

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_userprofile_created_via_signal_on_user_create():
    user = User.objects.create_user(email="carla@minbzk.nl", first_name="Carla", last_name="Carla")
    assert UserProfile.objects.filter(user=user).exists()


def test_login_signal_stores_sso_subject_from_session(rf):
    user = User.objects.create_user(email="dirk@minbzk.nl", first_name="Dirk", last_name="Das")
    request = rf.get("/")
    request.session = {settings.OIDC_SUBJECT_SESSION_KEY: "sub-dirk"}
    user_logged_in.send(sender=User, request=request, user=user)
    user.profile.refresh_from_db()
    assert user.profile.sso_subject == "sub-dirk"


def test_active_consent_is_unique_per_user_app(alice, mock_wies):
    Consent.objects.create(user=alice, application=mock_wies)
    with pytest.raises(IntegrityError), transaction.atomic():
        Consent.objects.create(user=alice, application=mock_wies)


def test_revoked_consent_allows_new_consent(alice, mock_wies):
    """Na intrekken mag dezelfde combinatie opnieuw aangemaakt worden."""
    old = Consent.objects.create(user=alice, application=mock_wies)
    old.revoked_at = timezone.now()
    old.save()
    Consent.objects.create(user=alice, application=mock_wies)
    assert Consent.objects.filter(user=alice, application=mock_wies).count() == 2
    assert Consent.objects.filter(user=alice, application=mock_wies, revoked_at__isnull=True).count() == 1


def test_consent_is_active_property(alice, mock_wies):
    c = Consent.objects.create(user=alice, application=mock_wies)
    assert c.is_active
    c.revoked_at = timezone.now()
    assert not c.is_active
