"""Seed demo-data voor PoC: 2 ambtenaren + per-app consents voor Wies.

Idempotent: opnieuw draaien is veilig (gebruikt get_or_create / update_or_create).
Applications worden geladen via `loaddata seed_apps` (zie justfile setup).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from rijksprofielservice.core.models import Application, Consent, UserProfile

User = get_user_model()

AMBTENAREN = [
    {
        "email": "kevin.popov@rijksoverheid.nl",
        "first_name": "Kevin",
        "last_name": "Popov",
        "sso_subject": "demo-sub-kevin",
        "telefoon": "06-4444-4444",
        "functie": "Beleidsadviseur",
        "organisatie": "Rijksoverheid",
        "consents_to": ["wies"],
    },
    {
        "email": "diana.bos@rijksoverheid.nl",
        "first_name": "Diana",
        "last_name": "Bos",
        "sso_subject": "demo-sub-diana",
        "telefoon": "06-5555-5555",
        "functie": "Programmamanager",
        "organisatie": "Rijksoverheid",
        "consents_to": ["wies"],
    },
]


class Command(BaseCommand):
    help = "Seed demo-data: 2 ambtenaren + consents voor Wies. Idempotent."

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
                # Bij nieuwe consent: granted_fields gelijk aan alles wat de app vraagt,
                # zodat de API direct profielvelden teruggeeft (anders zou granted_fields
                # leeg blijven door de model-default en zou de API niks delen).
                Consent.objects.get_or_create(
                    user=user,
                    application=app,
                    revoked_at=None,
                    defaults={"granted_fields": list(app.requested_fields or [])},
                )

        self.stdout.write(self.style.SUCCESS("Demo-data geseed."))
