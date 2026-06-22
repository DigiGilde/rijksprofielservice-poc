"""Custom OAuth Authorization View.

Subclass van django-oauth-toolkit's `AuthorizationView` die ons eigen Jinja2
consent-template gebruikt en de business-Application + effective_fields aan de
context toevoegt.
"""

from django.shortcuts import render
from oauth2_provider.models import get_application_model
from oauth2_provider.views import AuthorizationView

from .models import Application, Consent


class ProfielserviceAuthorizationView(AuthorizationView):
    template_name = "core/oauth_consent.html"

    def get(self, request, *args, **kwargs):
        client_id = request.GET.get("client_id", "")
        if not client_id or not get_application_model().objects.filter(client_id=client_id).exists():
            return render(
                request,
                "core/oauth_app_not_registered.html",
                {"client_id": client_id},
                status=400,
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dot_app = ctx.get("application")
        app = Application.objects.filter(oauth_app=dot_app).first() if dot_app else None
        ctx["app"] = app
        ctx["effective_fields"] = list(app.requested_fields) if app else []

        existing = None
        if app and self.request.user.is_authenticated:
            existing = (
                Consent.objects.filter(user=self.request.user, application=app, revoked_at__isnull=True)
                .only("granted_fields")
                .first()
            )
        ctx["existing_consent"] = existing
        return ctx

    def form_valid(self, form):
        if form.cleaned_data.get("allow"):
            client_id = form.cleaned_data.get("client_id")
            app = Application.objects.filter(oauth_app__client_id=client_id).first()
            allowed = set(app.requested_fields or []) if app else set()
            selected = [f for f in self.request.POST.getlist("granted_field") if f in allowed]
            if not selected:
                # Alles uitgevinkt → behandel als 'Weigeren': stille deny.
                form.cleaned_data["allow"] = False
            else:
                self.request.session[f"pending_consent_fields:{client_id}"] = selected
        return super().form_valid(form)
