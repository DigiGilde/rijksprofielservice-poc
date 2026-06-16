import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from .services.events import create_auth_event

logger = logging.getLogger(__name__)

User = get_user_model()


class AuthBackend(BaseBackend):
    def authenticate(self, request, username=None, email=None, first_name="", last_name="", **kwargs):
        # TODO: generaliseren — nu hardcoded op (username, email) voor de OIDC-flow,
        # waardoor andere backends (bv. ModelBackend voor /admin/ met username+password)
        # alleen werken via de fallback hieronder. Liever een expliciet contract.
        if not username or not email:
            return None

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            # Auto-provision: Keycloak is bron van waarheid voor identiteit.
            # Een succesvolle Keycloak-login impliceert dat de gebruiker bekend is bij SSO Rijk;
            # we maken hier het lokale spiegelrecord aan. post_save-signal maakt UserProfile.
            user = User.objects.create_user(email=email, first_name=first_name, last_name=last_name)
            logger.info("Auto-provisioned new user from SSO: %s", email)
            create_auth_event(email, "Login.provisioned")
            return user

        logger.info("user successfully authenticated")
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
