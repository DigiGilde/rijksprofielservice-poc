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
    """Een consuming app die toegang vraagt tot profielgegevens.

    Domeinmodel: source of truth voor `requested_fields`, `is_approved`, beschrijving.
    OAuth-protocolvelden (client_secret, redirect_uris, grant_type) leven op het
    gekoppelde `oauth2_provider.Application`. Voor consuming apps is er één
    Authorization Code client (FK `oauth_app`) en een tweede Client Credentials
    client met client_id `<client_id>-m2m` (los record, gelookupt in de M2M-flow).
    """

    naam = models.CharField(max_length=128, unique=True)
    # client_id van de Authorization Code OAuth-client; matcht oauth_app.client_id.
    client_id = models.CharField(max_length=128, unique=True)
    beschrijving = models.TextField(blank=True)
    # Lijst van veldnamen uit FIELD_CHOICES.
    requested_fields = models.JSONField(default=list)
    is_approved = models.BooleanField(default=False)
    # OAuth Authorization Code client (django-oauth-toolkit). Nullable zodat
    # bestaande records vóór migratie 0003 niet breken.
    oauth_app = models.OneToOneField(
        "oauth2_provider.Application",
        on_delete=models.PROTECT,
        related_name="profielservice_app",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.naam

    def save(self, *args, **kwargs):
        # Hou client_id gesynchroniseerd met de OAuth-client zodat lookups
        # (signal, admin, fixtures) één bron hebben.
        if self.oauth_app_id and self.oauth_app.client_id and self.client_id != self.oauth_app.client_id:
            self.client_id = self.oauth_app.client_id
        super().save(*args, **kwargs)


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
    # Subset van application.requested_fields waarvoor de gebruiker toestemming gaf.
    granted_fields = models.JSONField(default=list)

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
