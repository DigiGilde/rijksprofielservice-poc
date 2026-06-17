from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from oauth2_provider.signals import app_authorized

from rijksprofielservice.rijksauth.models import User

from .models import Application, Consent, UserProfile


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


@receiver(app_authorized)
def record_consent_on_authorize(sender, request, token, **kwargs):
    """Bij een succesvolle OAuth-grant: leg vast in eigen Consent-tabel.

    Token = bewijs van consent, en de DOT-grant zelf is de bron-of-truth voor
    toegang. We schaduwen alleen in de Consent-tabel zodat het beheerscherm
    (`consent-list`) en het revoke-pad simpel kunnen blijven werken.
    """
    if token is None or token.user is None or token.application is None:
        return
    app = Application.objects.filter(oauth_app=token.application).first()
    if app is None:
        return
    Consent.objects.get_or_create(user=token.user, application=app, revoked_at=None)
