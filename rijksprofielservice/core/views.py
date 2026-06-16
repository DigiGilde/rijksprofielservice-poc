import io
import json
import secrets
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_not_required
from django.core.management import call_command
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.test import Client as DjangoTestClient
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import AvatarForm, UserProfileForm
from .models import Application, Consent, UserProfile

OAUTH_SESSION_KEY = "oauth_authorize_params"


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


@require_POST
def consent_revoke(request, application_id):
    application = get_object_or_404(Application, pk=application_id)
    Consent.objects.filter(user=request.user, application=application, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
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


def _render_oauth_error(request, *, status, title, detail):
    return render(request, "core/oauth_error.html", {"title": title, "detail": detail}, status=status)


def _parse_requested_fields(raw):
    if not raw:
        return None
    return [f.strip() for f in raw.split(",") if f.strip()]


@require_GET
def oauth_authorize(request):
    """OAuth-style authorize entry: valideer params, sla op in session, redirect naar consent-scherm.

    PoC1 "light mimick" — geen code/token exchange. Echte OAuth Authorization Code
    flow tegen Keycloak is gepland voor PoC2 (zie planbestand).
    """
    client_id = request.GET.get("client_id")
    redirect_uri = request.GET.get("redirect_uri")
    state = request.GET.get("state", "")
    fields_param = _parse_requested_fields(request.GET.get("requested_fields"))

    if not client_id or not redirect_uri:
        return _render_oauth_error(
            request,
            status=400,
            title="Onvolledig verzoek",
            detail="client_id en redirect_uri zijn verplicht.",
        )

    app = Application.objects.filter(client_id=client_id).first()
    if app is None:
        return _render_oauth_error(
            request,
            status=400,
            title="Onbekende client",
            detail=f"client_id '{client_id}' is niet bekend.",
        )
    if not app.is_approved:
        return _render_oauth_error(
            request,
            status=403,
            title="Applicatie niet goedgekeurd",
            detail=f"{app.naam} is nog niet goedgekeurd door een beheerder.",
        )
    if not app.is_valid_redirect_uri(redirect_uri):
        return _render_oauth_error(
            request,
            status=400,
            title="Ongeldige redirect_uri",
            detail="Deze redirect_uri staat niet in de whitelist van de applicatie.",
        )

    allowed = set(app.requested_fields or [])
    if fields_param is not None:
        invalid = [f for f in fields_param if f not in allowed]
        if invalid:
            return _render_oauth_error(
                request,
                status=400,
                title="Ongeldige requested_fields",
                detail=f"Niet toegestaan voor deze applicatie: {', '.join(invalid)}",
            )
        effective_fields = [f for f in fields_param if f in allowed]
    else:
        effective_fields = list(app.requested_fields or [])

    request.session[OAUTH_SESSION_KEY] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "effective_fields": effective_fields,
    }
    return redirect("oauth-consent")


@require_GET
def oauth_consent_screen(request):
    params = request.session.get(OAUTH_SESSION_KEY)
    if not params:
        return _render_oauth_error(
            request,
            status=400,
            title="Geen lopend toestemmingsverzoek",
            detail="Start opnieuw via de consuming app.",
        )
    app = Application.objects.get(client_id=params["client_id"])
    return render(
        request,
        "core/oauth_consent.html",
        {"app": app, "effective_fields": params["effective_fields"], "state": params["state"]},
    )


@require_POST
def oauth_consent_decide(request):
    params = request.session.pop(OAUTH_SESSION_KEY, None)
    if not params:
        return _render_oauth_error(
            request,
            status=400,
            title="Sessie verlopen",
            detail="Start het toestemmingsverzoek opnieuw.",
        )
    app = Application.objects.get(client_id=params["client_id"])
    decision = request.POST.get("decision")

    qs_params = {"state": params["state"]}
    if decision == "grant":
        # Re-grant na revoke: nieuwe rij, oude blijft staan voor audit
        # (UniqueConstraint allows omdat oude rij revoked_at NOT NULL heeft).
        Consent.objects.get_or_create(user=request.user, application=app, revoked_at=None)
        qs_params["consent"] = "granted"
        # Geef de subject_id mee zodat de consuming app weet welk profiel ze mag opvragen.
        profile = getattr(request.user, "profile", None)
        sso_subject = profile.sso_subject if profile else ""
        if sso_subject:
            qs_params["subject_id"] = sso_subject
    else:
        qs_params["consent"] = "denied"

    qs = urlencode(qs_params)
    sep = "&" if "?" in params["redirect_uri"] else "?"
    return HttpResponseRedirect(f"{params['redirect_uri']}{sep}{qs}")


def _mock_landing(request, *, client_id, app_label):
    """Demo-landing voor mock consuming app.

    Toont de inkomende query-params (oauth-roundtrip resultaat), een knop om de flow
    te starten, en — na een 'granted' consent — een knop om server-side de batch-API
    aan te roepen met een via mint_test_token gemunte JWT.
    """
    incoming = dict(request.GET.items())

    landing_url = request.build_absolute_uri(request.path)
    fresh_state = secrets.token_urlsafe(16)
    authorize_url = (
        request.build_absolute_uri("/oauth/authorize")
        + "?"
        + urlencode({"client_id": client_id, "redirect_uri": landing_url, "state": fresh_state})
    )

    api_result = None
    if request.method == "POST" and request.POST.get("action") == "call-api":
        buf = io.StringIO()
        call_command("mint_test_token", app=client_id, stdout=buf)
        token = buf.getvalue().strip()
        # Prefer subject_id uit de OAuth-redirect (realistisch consuming-app gedrag);
        # val terug op de eigen sso_subject voor demo zonder OAuth-roundtrip.
        sub = request.POST.get("subject_id") or (
            request.user.profile.sso_subject
            if hasattr(request.user, "profile") and request.user.profile.sso_subject
            else str(request.user.pk)
        )
        test_client = DjangoTestClient()
        resp = test_client.post(
            "/api/v1/profiles/batch",
            data=json.dumps({"subject_ids": [sub]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=request.get_host(),
        )
        try:
            body = resp.json()
        except ValueError:
            body = resp.content.decode("utf-8", errors="replace")
        api_result = {"status": resp.status_code, "body": body, "subject_id": sub}

    return render(
        request,
        "core/mock_landing.html",
        {
            "app_label": app_label,
            "client_id": client_id,
            "incoming": incoming,
            "authorize_url": authorize_url,
            "fresh_state": fresh_state,
            "api_result": api_result,
        },
    )


def mock_wies_landing(request):
    return _mock_landing(request, client_id="mock-wies", app_label="Mock Wies")


def mock_amt_landing(request):
    return _mock_landing(request, client_id="mock-amt", app_label="Mock AMT")
