from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    name = "apps.realtime"
    label = "realtime"
    verbose_name = "Realtime"

    def ready(self) -> None:
        from . import mappers  # noqa: F401 — registers event mappers
