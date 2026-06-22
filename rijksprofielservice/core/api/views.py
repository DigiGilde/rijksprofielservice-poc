from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_not_required
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from rijksprofielservice.core.models import APIRequest, Application, UserProfile

from .serializers import build_profile_response, fields_for_app_and_user

User = get_user_model()


def _lookup_user(subject_id: str):
    """Zoek user op SSO subject (opgeslagen op UserProfile)."""
    return User.objects.filter(profile__sso_subject=subject_id).first()


def _business_app(request) -> Application | None:
    """Vind de business-Application bij de OAuth-token op het request.

    `request.auth` is een `oauth2_provider.AccessToken`. Voor user-bound tokens
    (Authorization Code) wijst `token.application` direct naar de auth-code
    DOT-Application. Voor M2M-tokens wijst hij naar de `-m2m`-variant; daar
    valt het client_id-suffix vanaf om de business-app te vinden.

    Niet-goedgekeurde apps (`is_approved=False`) worden geweerd — extra laag
    bovenop de DOT-clientvalidatie zodat admin-blokkade direct effect heeft.
    """
    token = request.auth
    if token is None or token.application is None:
        return None
    dot_app = token.application
    app = Application.objects.filter(oauth_app=dot_app).first()
    if app is None:
        client_id = dot_app.client_id
        if client_id.endswith("-m2m"):
            app = Application.objects.filter(client_id=client_id[: -len("-m2m")]).first()
    if app is None or not app.is_approved:
        return None
    return app


def _is_user_token(request) -> bool:
    return getattr(request.auth, "user_id", None) is not None


@method_decorator(login_not_required, name="dispatch")
class ProfileMeView(APIView):
    """Profiel van de ingelogde ambtenaar — vereist een user-bound (Authorization Code) token."""

    required_scopes = ["read_profile"]

    def get(self, request):
        if not _is_user_token(request):
            return Response({"detail": "User-bound token vereist"}, status=status.HTTP_403_FORBIDDEN)
        app = _business_app(request)
        if app is None:
            return Response({"detail": "Onbekende applicatie"}, status=status.HTTP_403_FORBIDDEN)

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        APIRequest.objects.create(application=app, subject_ids=[profile.sso_subject or str(request.user.pk)])
        fields = fields_for_app_and_user(app, request.user.id)
        if fields is None:
            return Response({"detail": "Geen toestemming"}, status=status.HTTP_403_FORBIDDEN)
        body = build_profile_response(profile, fields, request)
        # `subject_id` is geen profielveld maar token-metadata: het laat de consuming
        # app weten welke SSO-identiteit bij dit token hoort, zodat ze die kunnen
        # opslaan voor latere M2M-batch-calls. Niet onderworpen aan field-filtering.
        body["subject_id"] = profile.sso_subject
        return Response(body)


@method_decorator(login_not_required, name="dispatch")
class ProfileDetailView(APIView):
    required_scopes = ["read_profile"]

    def get(self, request, subject_id):
        if _is_user_token(request):
            return Response({"detail": "Client-credentials token vereist"}, status=status.HTTP_403_FORBIDDEN)
        app = _business_app(request)
        if app is None:
            return Response({"detail": "Onbekende applicatie"}, status=status.HTTP_403_FORBIDDEN)
        APIRequest.objects.create(application=app, subject_ids=[subject_id])

        user = _lookup_user(subject_id)
        if user is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        fields = fields_for_app_and_user(app, user.id)
        if fields is None:
            return Response({"detail": "Geen toestemming"}, status=status.HTTP_403_FORBIDDEN)

        profile, _ = UserProfile.objects.get_or_create(user=user)
        return Response(build_profile_response(profile, fields, request))


@method_decorator(login_not_required, name="dispatch")
class ProfileBatchView(APIView):
    required_scopes = ["read_profile"]

    def post(self, request):
        if _is_user_token(request):
            return Response({"detail": "Client-credentials token vereist"}, status=status.HTTP_403_FORBIDDEN)
        app = _business_app(request)
        if app is None:
            return Response({"detail": "Onbekende applicatie"}, status=status.HTTP_403_FORBIDDEN)

        subject_ids = request.data.get("subject_ids", [])
        if not isinstance(subject_ids, list):
            return Response(
                {"detail": "subject_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        APIRequest.objects.create(application=app, subject_ids=subject_ids)

        profiles: dict[str, dict | None] = {}
        for subject_id in subject_ids:
            user = _lookup_user(subject_id)
            if user is None:
                profiles[subject_id] = None
                continue
            fields = fields_for_app_and_user(app, user.id)
            if fields is None:
                profiles[subject_id] = None
                continue
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profiles[subject_id] = build_profile_response(profile, fields, request)

        return Response({"profiles": profiles})
