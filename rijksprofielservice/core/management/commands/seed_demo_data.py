"""Seed demo-data voor PoC1: 3 ambtenaren + per-app consents.

Idempotent: opnieuw draaien is veilig (gebruikt get_or_create / update_or_create).
Applications worden geladen via `loaddata seed_apps` (zie justfile setup).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from rijksprofielservice.core.models import Application, Consent, UserProfile

User = get_user_model()

AMBTENAREN = [
    {
        "email": "alice@minbzk.nl",
        "first_name": "Alice",
        "last_name": "Aap",
        "sso_subject": "demo-sub-alice",
        "telefoon": "06-1111-1111",
        "functie": "Beleidsmedewerker",
        "organisatie": "BZK",
        "consents_to": ["mock-wies"],
    },
    {
        "email": "bob@minbzk.nl",
        "first_name": "Bob",
        "last_name": "Beer",
        "sso_subject": "demo-sub-bob",
        "telefoon": "06-2222-2222",
        "functie": "Adviseur",
        "organisatie": "BZK",
        "consents_to": ["mock-amt"],
    },
    {
        "email": "carol@minfin.nl",
        "first_name": "Carol",
        "last_name": "Citroen",
        "sso_subject": "demo-sub-carol",
        "telefoon": "06-3333-3333",
        "functie": "Senior Inspecteur",
        "organisatie": "Financiën",
        "consents_to": ["mock-wies", "mock-amt"],
    },
]


class Command(BaseCommand):
    help = "Seed demo-data: 3 ambtenaren + consents. Idempotent."

    def handle(self, *args, **options):
        apps_by_client_id = {a.client_id: a for a in Application.objects.all()}
        if not apps_by_client_id:
            msg = "Geen Applications gevonden. Draai eerst: manage.py loaddata seed_apps"
            raise CommandError(msg)

        for spec in AMBTENAREN:
            existing = User.objects.filter(email__iexact=spec["email"]).first()
            if existing is None:
                user = User.objects.create_user(
                    email=spec["email"],
                    first_name=spec["first_name"],
                    last_name=spec["last_name"],
                )
                self.stdout.write(f"User aangemaakt: {spec['email']}")
            else:
                user = existing

            # post_save signal heeft profiel al aangemaakt; vul de velden.
            UserProfile.objects.filter(user=user).update(
                sso_subject=spec["sso_subject"],
                telefoon=spec["telefoon"],
                functie=spec["functie"],
                organisatie=spec["organisatie"],
            )

            for client_id in spec["consents_to"]:
                app = apps_by_client_id.get(client_id)
                if app is None:
                    self.stdout.write(self.style.WARNING(f"  Application {client_id} niet gevonden, overslaan"))
                    continue
                # Actieve consent = revoked_at IS NULL. Get-or-create voorkomt duplicates.
                Consent.objects.get_or_create(
                    user=user,
                    application=app,
                    revoked_at=None,
                )

        self.stdout.write(self.style.SUCCESS("Demo-data geseed."))
