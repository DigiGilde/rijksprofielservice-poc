"""URL configuration for rijksprofielservice."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from rijksprofielservice.core import views as core_views
from rijksprofielservice.core.api.views import ProfileBatchView, ProfileDetailView
from rijksprofielservice.rijksauth.views import auth, login, logout

urlpatterns = [
    path("admin/", admin.site.urls),
    # Auth (rijksauth)
    path("inloggen/", login, name="login"),
    path("uitloggen/", logout, name="logout"),
    path("auth/", auth, name="auth"),
    path("geen-toegang/", core_views.no_access, name="no-access"),
    # Profielservice UI
    path("", RedirectView.as_view(pattern_name="profile-edit", permanent=False), name="home"),
    path("profiel/", core_views.profile_edit, name="profile-edit"),
    path("profiel/foto/", core_views.avatar_update, name="avatar-update"),
    path("profiel/foto/verwijderen/", core_views.avatar_delete, name="avatar-delete"),
    path("toestemmingen/", core_views.consent_list, name="consent-list"),
    path("toestemmingen/<int:application_id>/intrekken/", core_views.consent_revoke, name="consent-revoke"),
    # Avatar serving
    path("avatars/<int:user_id>.jpg", core_views.avatar, name="avatar"),
    # REST API — batch route VOOR de detail route, anders matcht "batch" als subject_id.
    path("api/v1/profiles/batch", ProfileBatchView.as_view(), name="api-profile-batch"),
    path("api/v1/profiles/<str:subject_id>", ProfileDetailView.as_view(), name="api-profile-detail"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
