"""Application → oauth2_provider.Application koppeling + verwijder eigen redirect_uris.

Voor elke bestaande `Application` worden twee DOT-Applications aangemaakt:
- `<client_id>` met grant_type=authorization-code (gekoppeld via FK `oauth_app`)
- `<client_id>-m2m` met grant_type=client-credentials (los record, gevonden via client_id-lookup)

Client-secrets komen uit een dict-fallback (PoC) zodat seeds reproduceerbaar zijn.
"""

import secrets
from django.db import migrations, models


# PoC-vaste secrets per app. Niet voor productie — daar worden ze via admin/CLI
# gegenereerd. Synced met `seed_apps.json` zodat lokale demos reproduceerbaar zijn.
DEFAULT_M2M_SECRETS = {
    "mock-wies": "local-dev-secret-wies",
    "mock-amt": "local-dev-secret-amt",
}


def create_oauth_apps(apps, schema_editor):
    Application = apps.get_model("core", "Application")
    DotApplication = apps.get_model("oauth2_provider", "Application")

    for app in Application.objects.all():
        redirect_uris_str = "\n".join(app.redirect_uris or [])

        auth_code_app, _ = DotApplication.objects.get_or_create(
            client_id=app.client_id,
            defaults={
                "name": app.naam,
                "client_type": "confidential",
                "authorization_grant_type": "authorization-code",
                "client_secret": DEFAULT_M2M_SECRETS.get(app.client_id, secrets.token_urlsafe(32)),
                "redirect_uris": redirect_uris_str,
                "skip_authorization": False,
                "algorithm": "",
            },
        )
        app.oauth_app = auth_code_app
        app.save(update_fields=["oauth_app"])

        DotApplication.objects.get_or_create(
            client_id=f"{app.client_id}-m2m",
            defaults={
                "name": f"{app.naam} (M2M)",
                "client_type": "confidential",
                "authorization_grant_type": "client-credentials",
                "client_secret": DEFAULT_M2M_SECRETS.get(app.client_id, secrets.token_urlsafe(32)),
                "redirect_uris": "",
                "skip_authorization": True,
                "algorithm": "",
            },
        )


def remove_oauth_apps(apps, schema_editor):
    Application = apps.get_model("core", "Application")
    DotApplication = apps.get_model("oauth2_provider", "Application")

    for app in Application.objects.all():
        DotApplication.objects.filter(client_id=f"{app.client_id}-m2m").delete()
        if app.oauth_app_id:
            dot_app_id = app.oauth_app_id
            app.oauth_app = None
            app.save(update_fields=["oauth_app"])
            DotApplication.objects.filter(pk=dot_app_id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_application_redirect_uris"),
        ("oauth2_provider", "0014_alter_help_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="oauth_app",
            field=models.OneToOneField(
                null=True,
                blank=True,
                on_delete=models.PROTECT,
                related_name="profielservice_app",
                to="oauth2_provider.application",
            ),
        ),
        migrations.RunPython(create_oauth_apps, remove_oauth_apps),
        migrations.RemoveField(
            model_name="application",
            name="redirect_uris",
        ),
    ]
