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
    """Returns de overlap van app-requested_fields en actieve user-consent.granted_fields.

    None betekent: geen actieve consent — caller serveert `null` in batch response of
    een 403. Volgorde van `application.requested_fields` blijft behouden.
    """
    consent = (
        Consent.objects.filter(user_id=user_id, application=application, revoked_at__isnull=True)
        .only("granted_fields")
        .first()
    )
    if consent is None:
        return None
    granted = set(consent.granted_fields or [])
    return [f for f in (application.requested_fields or []) if f in granted]
