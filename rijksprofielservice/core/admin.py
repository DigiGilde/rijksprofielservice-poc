from django.contrib import admin

from .models import APIRequest, Application, Consent, UserProfile


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("naam", "client_id", "oauth_app", "is_approved", "created_at")
    list_filter = ("is_approved",)
    search_fields = ("naam", "client_id")
    raw_id_fields = ("oauth_app",)
    actions = ["approve_apps"]

    @admin.action(description="Goedkeuren")
    def approve_apps(self, request, queryset):
        queryset.update(is_approved=True)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "functie", "organisatie", "updated_at")
    search_fields = ("user__email", "functie", "organisatie")


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "application", "granted_at", "revoked_at")
    list_filter = ("application", "revoked_at")
    search_fields = ("user__email", "application__naam")


@admin.register(APIRequest)
class APIRequestAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "application", "request_id")
    list_filter = ("application",)
    readonly_fields = ("request_id", "timestamp", "application", "subject_ids")
