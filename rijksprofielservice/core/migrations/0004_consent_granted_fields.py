"""Per-veld consent: voeg `granted_fields` toe en backfill bestaande actieve rijen.

Bestaande Consent-rijen krijgen `granted_fields = application.requested_fields`,
zodat het huidige (alles-of-niets) gedrag behouden blijft tot een gebruiker zelf
zijn keuze aanpast via de Toestemmingen-pagina.
"""

from django.db import migrations, models


def backfill_granted_fields(apps, schema_editor):
    Consent = apps.get_model("core", "Consent")
    for c in Consent.objects.filter(revoked_at__isnull=True).select_related("application"):
        c.granted_fields = list(c.application.requested_fields or [])
        c.save(update_fields=["granted_fields"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_application_oauth_app"),
    ]

    operations = [
        migrations.AddField(
            model_name="consent",
            name="granted_fields",
            field=models.JSONField(default=list),
        ),
        migrations.RunPython(backfill_granted_fields, migrations.RunPython.noop),
    ]
