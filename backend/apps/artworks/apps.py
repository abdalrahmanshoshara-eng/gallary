from django.apps import AppConfig


class ArtworksConfig(AppConfig):
    name = "apps.artworks"
    label = "artworks"
    verbose_name = "الأعمال الفنية"

    def ready(self) -> None:
        from . import signals  # noqa: F401
