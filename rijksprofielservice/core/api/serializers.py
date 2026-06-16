"""Profielserialisatie: alleen velden waar de app toestemming voor heeft."""

from django.urls import reverse

from rijksprofielservice.core.models import Application, Consent, UserProfile


def build_profile_response(profile: UserProfile, fields: list[str], request=None) -> dict:
    """Geef alleen de gevraagde velden terug.

    `fields` is `Application.requested_fields ∩ Consent` — al gefilterd door caller.
    """
    user = profile.user
    out: dict = {}
    if "naam" in fields:
        out["naam"] = f"{user.first_name} {user.last_name}".strip() or user.email
    if "email" in fields:
        out["email"] = user.email
    if "telefoon" in fields:
        out["telefoon"] = profile.telefoon
    if "functie" in fields:
        out["functie"] = profile.functie
    if "organisatie" in fields:
        out["organisatie"] = profile.organisatie
    if "avatar" in fields and profile.avatar:
        path = reverse("avatar", args=[user.id])
        out["avatar_url"] = request.build_absolute_uri(path) if request else path
    return out


def fields_for_app_and_user(application: Application, user_id: int) -> list[str] | None:
    """Returns de overlap van app-requested_fields en actieve user-consent.

    None betekent: geen actieve consent — caller serveert `null` in batch response.
    """
    has_consent = Consent.objects.filter(
        user_id=user_id, application=application, revoked_at__isnull=True
    ).exists()
    if not has_consent:
        return None
    return list(application.requested_fields)
