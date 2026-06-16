import uuid

from django.conf import settings
from django.db import models


def avatar_upload_path(instance, filename):
    return f"avatars/{instance.user_id}.jpg"


class UserProfile(models.Model):
    """Profielgegevens van een ambtenaar.

    De basisvelden (naam, email) leven op het User-model (rijksauth) en komen
    uit SSO. Hier staan de door de gebruiker zelf beheerde velden.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    # SSO subject (Keycloak `sub`) — opgeslagen op het profiel, niet op User,
    # zodat rijksauth generiek blijft. Wordt gevuld op login via signal.
    sso_subject = models.CharField(max_length=255, blank=True, db_index=True)
    telefoon = models.CharField(max_length=32, blank=True)
    functie = models.CharField(max_length=128, blank=True)
    organisatie = models.CharField(max_length=128, blank=True)
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profiel van {self.user.email}"


# Welke profielvelden mag een consuming app aanvragen?
FIELD_CHOICES = [
    ("naam", "Naam"),
    ("email", "E-mailadres"),
    ("telefoon", "Telefoonnummer"),
    ("functie", "Functie"),
    ("organisatie", "Organisatie"),
    ("avatar", "Avatar / foto"),
]


class Application(models.Model):
    """Een consuming app die toegang vraagt tot profielgegevens."""

    naam = models.CharField(max_length=128, unique=True)
    # client_id uit de profielservice Keycloak realm; matcht JWT `azp` claim.
    client_id = models.CharField(max_length=128, unique=True)
    beschrijving = models.TextField(blank=True)
    # Lijst van veldnamen uit FIELD_CHOICES.
    requested_fields = models.JSONField(default=list)
    is_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.naam


class Consent(models.Model):
    """Toestemming van een gebruiker voor een specifieke app.

    Soft-revoke: bij intrekken zetten we `revoked_at` zodat we audit-info houden.
    Per (user, application) is er maximaal één actieve (revoked_at IS NULL) rij.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consents",
    )
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="consents")
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "application"],
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_consent_per_user_app",
            ),
        ]

    @property
    def is_active(self):
        return self.revoked_at is None

    def __str__(self):
        state = "actief" if self.is_active else f"ingetrokken {self.revoked_at:%Y-%m-%d}"
        return f"{self.user.email} → {self.application.naam} ({state})"


class APIRequest(models.Model):
    """Simpele audit-log van API-calls — handig voor de PoC-demo.

    Bewaart welke app welke subject-ids opvroeg. Wordt in PoC2 vervangen door
    een volwassener audit log.
    """

    request_id = models.UUIDField(default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.SET_NULL, null=True, blank=True)
    subject_ids = models.JSONField(default=list)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
