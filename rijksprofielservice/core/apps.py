from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rijksprofielservice.core"
    label = "core"

    def ready(self):
        from . import signals  # noqa: F401, PLC0415
