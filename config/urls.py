"""URL configuration for rijksprofielservice."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from rijksprofielservice.core import views as core_views
from rijksprofielservice.core.api.views import ProfileBatchView, ProfileDetailView, ProfileMeView
from rijksprofielservice.core.oauth_views import ProfielserviceAuthorizationView
from rijksprofielservice.rijksauth.views import auth, login, logout

urlpatterns = [
    path("admin/", admin.site.urls),
    # Auth (rijksauth)
    path("inloggen/", login, name="login"),
    path("uitloggen/", logout, name="logout"),
    path("auth/", auth, name="auth"),
    path("geen-toegang/", core_views.no_access, name="no-access"),
    path("privacy/", core_views.privacy, name="privacy"),
    path("docs/", core_views.docs_index, name="docs-index"),
    path("docs/<slug:slug>/", core_views.docs_detail, name="docs-detail"),
    # Profielservice UI
    path("", RedirectView.as_view(pattern_name="profile-edit", permanent=False), name="home"),
    path("profiel/", core_views.profile_edit, name="profile-edit"),
    path("profiel/foto/", core_views.avatar_update, name="avatar-update"),
    path("profiel/foto/verwijderen/", core_views.avatar_delete, name="avatar-delete"),
    path("toestemmingen/", core_views.consent_list, name="consent-list"),
    path("toestemmingen/<int:application_id>/bewerken/", core_views.consent_edit, name="consent-edit"),
    path("toestemmingen/<int:application_id>/intrekken/", core_views.consent_revoke, name="consent-revoke"),
    path("toestemmingen/<int:application_id>/opslaan/", core_views.consent_update, name="consent-update"),
    path("applicaties/", core_views.application_list, name="application-list"),
    path("applicaties/nieuw/", core_views.application_create, name="application-create"),
    path("applicaties/<int:pk>/bewerken/", core_views.application_edit, name="application-edit"),
    path("applicaties/<int:pk>/verwijderen/", core_views.application_delete, name="application-delete"),
    # OAuth Authorization Server (django-oauth-toolkit). Onze custom authorize-view
    # eerst registreren zodat hij wint van de default in `oauth2_provider.urls`.
    path("o/authorize/", ProfielserviceAuthorizationView.as_view(), name="oauth2_provider_authorize"),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    # Avatar serving
    path("avatars/<int:user_id>.jpg", core_views.avatar, name="avatar"),
    # REST API — meer-specifieke routes eerst.
    path("api/v1/profiles/me", ProfileMeView.as_view(), name="api-profile-me"),
    path("api/v1/profiles/batch", ProfileBatchView.as_view(), name="api-profile-batch"),
    path("api/v1/profiles/<str:subject_id>", ProfileDetailView.as_view(), name="api-profile-detail"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
