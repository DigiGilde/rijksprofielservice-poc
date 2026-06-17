"""Custom OAuth Authorization View.

Subclass van django-oauth-toolkit's `AuthorizationView` die ons eigen Jinja2
consent-template gebruikt en de business-Application + effective_fields aan de
context toevoegt.
"""

from oauth2_provider.views import AuthorizationView

from .models import Application


class ProfielserviceAuthorizationView(AuthorizationView):
    template_name = "core/oauth_consent.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dot_app = ctx.get("application")
        app = Application.objects.filter(oauth_app=dot_app).first() if dot_app else None
        ctx["app"] = app
        ctx["effective_fields"] = list(app.requested_fields) if app else []
        return ctx
