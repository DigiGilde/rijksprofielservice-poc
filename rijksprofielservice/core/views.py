import secrets

from django.contrib.auth.decorators import login_not_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from oauth2_provider.models import get_application_model

from .forms import ApplicationCreateForm, ApplicationEditForm, AvatarForm, UserProfileForm
from .models import Application, Consent, UserProfile


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def profile_edit(request):
    profile = _get_or_create_profile(request.user)
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("profile-edit")
    else:
        form = UserProfileForm(instance=profile)
    return render(request, "core/profile_edit.html", {"form": form, "profile": profile})


@require_POST
def avatar_update(request):
    """Upload (of vervang) avatar — direct, geen aparte 'Opslaan' nodig."""
    profile = _get_or_create_profile(request.user)
    old_avatar_name = profile.avatar.name if profile.avatar else None
    form = AvatarForm(request.POST, request.FILES, instance=profile)
    if form.is_valid():
        form.save()
        if old_avatar_name:
            form.instance.avatar.storage.delete(old_avatar_name)
    return redirect("profile-edit")


@require_POST
def avatar_delete(request):
    """Verwijder avatar — direct, geen aparte 'Opslaan' nodig."""
    profile = _get_or_create_profile(request.user)
    if profile.avatar:
        profile.avatar.delete(save=True)
    return redirect("profile-edit")


def consent_list(request):
    consents = (
        Consent.objects.filter(user=request.user, revoked_at__isnull=True)
        .select_related("application")
        .order_by("application__naam")
    )
    return render(request, "core/consent_list.html", {"consents": consents})


def consent_edit(request, application_id):
    application = get_object_or_404(Application, pk=application_id)
    consent = get_object_or_404(
        Consent, user=request.user, application=application, revoked_at__isnull=True
    )
    return render(request, "core/consent_edit.html", {"consent": consent, "application": application})


@require_POST
def consent_revoke(request, application_id):
    application = get_object_or_404(Application, pk=application_id)
    Consent.objects.filter(user=request.user, application=application, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    # Trek ook alle OAuth-grants/tokens van deze user voor deze app in, zodat
    # bestaande access tokens direct ongeldig worden — niet pas na expiry.
    if application.oauth_app_id:
        from oauth2_provider.models import AccessToken, Grant, RefreshToken

        AccessToken.objects.filter(user=request.user, application_id=application.oauth_app_id).delete()
        RefreshToken.objects.filter(user=request.user, application_id=application.oauth_app_id).delete()
        Grant.objects.filter(user=request.user, application_id=application.oauth_app_id).delete()
    return redirect("consent-list")


@require_POST
def consent_update(request, application_id):
    """Sla per-veld toestemming op. Lege selectie = intrekken (delegate naar revoke)."""
    application = get_object_or_404(Application, pk=application_id)
    allowed = set(application.requested_fields or [])
    selected = [f for f in request.POST.getlist("granted_field") if f in allowed]
    if not selected:
        return consent_revoke(request, application_id)
    Consent.objects.filter(user=request.user, application=application, revoked_at__isnull=True).update(
        granted_fields=selected
    )
    return redirect("consent-list")


@login_not_required
def avatar(request, user_id):
    """Avatar serving op aparte URL, los van auth — caching-vriendelijk.

    Auth-laag komt later: PoC1 serveert public bytes met lange cache.
    """
    try:
        profile = UserProfile.objects.select_related("user").get(user_id=user_id)
    except UserProfile.DoesNotExist as exc:
        raise Http404 from exc
    if not profile.avatar:
        raise Http404
    response = FileResponse(profile.avatar.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "public, max-age=86400"
    return response


@login_not_required
def no_access(request):
    failed_email = request.session.pop("failed_login_email", "")
    return HttpResponse(
        f"Geen toegang voor {failed_email or 'onbekende gebruiker'}. Neem contact op met de beheerder.",
        status=403,
    )


@login_not_required
def privacy(request):
    return render(request, "core/privacy.html")


def application_list(request):
    apps = Application.objects.select_related("oauth_app").order_by("naam")
    return render(request, "core/application_list.html", {"apps": apps})


def application_create(request):
    if request.method == "POST":
        form = ApplicationCreateForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            DotApp = get_application_model()
            with transaction.atomic():
                auth_client = DotApp.objects.create(
                    client_id=cd["client_id"],
                    client_secret=secrets.token_urlsafe(32),
                    hash_client_secret=False,
                    name=cd["naam"],
                    redirect_uris=cd["redirect_uri"],
                    client_type="confidential",
                    authorization_grant_type="authorization-code",
                    skip_authorization=False,
                )
                DotApp.objects.create(
                    client_id=f"{cd['client_id']}-m2m",
                    client_secret=secrets.token_urlsafe(32),
                    hash_client_secret=False,
                    name=f"{cd['naam']} (M2M)",
                    redirect_uris="",
                    client_type="confidential",
                    authorization_grant_type="client-credentials",
                    skip_authorization=True,
                )
                app = Application.objects.create(
                    naam=cd["naam"],
                    client_id=cd["client_id"],
                    beschrijving=cd["beschrijving"],
                    requested_fields=cd["requested_fields"],
                    is_approved=cd["is_approved"],
                    oauth_app=auth_client,
                )
            return redirect("application-edit", pk=app.pk)
    else:
        form = ApplicationCreateForm()
    return render(request, "core/application_form.html", {"form": form, "mode": "create"})


def application_edit(request, pk):
    app = get_object_or_404(Application.objects.select_related("oauth_app"), pk=pk)
    m2m = get_application_model().objects.filter(client_id=f"{app.client_id}-m2m").first()
    if request.method == "POST":
        # Snapshot vóór form.is_valid(): ModelForm overschrijft `app.requested_fields`
        # tijdens _post_clean met de POST-waarden.
        previous_fields = set(app.requested_fields or [])
        form = ApplicationEditForm(request.POST, instance=app)
        if form.is_valid():
            removed = previous_fields - set(form.cleaned_data["requested_fields"])
            if removed and not request.POST.get("confirm_remove"):
                # Toon waarschuwing: bestaande consents worden gesnoeid.
                affected = Consent.objects.filter(application=app, revoked_at__isnull=True).count()
                return render(
                    request,
                    "core/application_remove_fields_confirm.html",
                    {
                        "app": app,
                        "removed_fields": sorted(removed),
                        "affected_consents": affected,
                        "post_data": request.POST,
                    },
                )
            form.save()
            return redirect("application-edit", pk=app.pk)
    else:
        form = ApplicationEditForm(instance=app)
    return render(
        request,
        "core/application_form.html",
        {"form": form, "mode": "edit", "app": app, "auth_client": app.oauth_app, "m2m_client": m2m},
    )


@require_POST
def application_delete(request, pk):
    app = get_object_or_404(Application.objects.select_related("oauth_app"), pk=pk)
    DotApp = get_application_model()
    with transaction.atomic():
        from oauth2_provider.models import AccessToken, Grant, RefreshToken

        m2m = DotApp.objects.filter(client_id=f"{app.client_id}-m2m").first()
        oauth_ids = [oid for oid in (app.oauth_app_id, m2m.id if m2m else None) if oid is not None]
        if oauth_ids:
            AccessToken.objects.filter(application_id__in=oauth_ids).delete()
            RefreshToken.objects.filter(application_id__in=oauth_ids).delete()
            Grant.objects.filter(application_id__in=oauth_ids).delete()
        Consent.objects.filter(application=app).delete()
        oauth_app = app.oauth_app
        app.delete()
        if oauth_app:
            oauth_app.delete()
        if m2m:
            m2m.delete()
    return redirect("application-list")


