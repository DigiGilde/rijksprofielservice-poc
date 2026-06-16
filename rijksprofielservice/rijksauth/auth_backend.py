import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from .services.events import create_auth_event

logger = logging.getLogger(__name__)

User = get_user_model()


class AuthBackend(BaseBackend):
    def authenticate(self, request, username=None, email=None, **kwargs):
        # TODO: generaliseren — nu hardcoded op (username, email) voor de OIDC-flow,
        # waardoor andere backends (bv. ModelBackend voor /admin/ met username+password)
        # alleen werken via de fallback hieronder. Liever een expliciet contract.
        if not username or not email:
            return None

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            logger.info("User not authenticated, user not known.")
            create_auth_event(email, "Login.fail", {"reason": "Unknown user"})
            return None

        logger.info("user successfully authenticated")
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
