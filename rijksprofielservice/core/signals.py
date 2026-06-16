from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from rijksprofielservice.rijksauth.models import User

from .models import UserProfile


@receiver(user_logged_in)
def ensure_profile_on_login(sender, request, user, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    # rijksauth heeft `sub` net in de session gezet — bewaar hem op het profiel
    # zodat de batch-API users via SSO-subject kan opzoeken.
    sub = request.session.get(settings.OIDC_SUBJECT_SESSION_KEY) if request else None
    if sub and profile.sso_subject != sub:
        profile.sso_subject = sub
        profile.save(update_fields=["sso_subject"])


@receiver(post_save, sender=User)
def ensure_profile_on_user_create(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
