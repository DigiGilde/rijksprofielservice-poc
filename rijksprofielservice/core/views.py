from django.contrib.auth.decorators import login_not_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AvatarForm, UserProfileForm
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
