from django.apps import AppConfig


class AuctionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auctions"
    verbose_name = "المزادات"

    def ready(self) -> None:
        from . import signals  # noqa: F401
