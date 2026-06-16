from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_not_required
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from rijksprofielservice.core.models import APIRequest, UserProfile

from .serializers import build_profile_response, fields_for_app_and_user

User = get_user_model()


def _lookup_user(subject_id: str):
    """Zoek user op SSO subject (opgeslagen op UserProfile).

    Fallback voor PoC1: seed-gebruikers die nog niet via OIDC zijn ingelogd
    hebben geen `sso_subject` — dan mag een numerieke string als user-pk werken.
    """
    user = User.objects.filter(profile__sso_subject=subject_id).first()
    if user is None and subject_id.isdigit():
        user = User.objects.filter(pk=int(subject_id)).first()
    return user


@method_decorator(login_not_required, name="dispatch")
class ProfileDetailView(APIView):
    def get(self, request, subject_id):
        consuming_app = request.user.application
        APIRequest.objects.create(application=consuming_app, subject_ids=[subject_id])

        user = _lookup_user(subject_id)
        if user is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        fields = fields_for_app_and_user(consuming_app, user.id)
        if fields is None:
            return Response({"detail": "Geen toestemming"}, status=status.HTTP_403_FORBIDDEN)

        profile, _ = UserProfile.objects.get_or_create(user=user)
        return Response(build_profile_response(profile, fields, request))


@method_decorator(login_not_required, name="dispatch")
class ProfileBatchView(APIView):
    def post(self, request):
        consuming_app = request.user.application
        subject_ids = request.data.get("subject_ids", [])
        if not isinstance(subject_ids, list):
            return Response(
                {"detail": "subject_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        APIRequest.objects.create(application=consuming_app, subject_ids=subject_ids)

        profiles: dict[str, dict | None] = {}
        for subject_id in subject_ids:
            user = _lookup_user(subject_id)
            if user is None:
                profiles[subject_id] = None
                continue
            fields = fields_for_app_and_user(consuming_app, user.id)
            if fields is None:
                profiles[subject_id] = None
                continue
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profiles[subject_id] = build_profile_response(profile, fields, request)

        return Response({"profiles": profiles})
