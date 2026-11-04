from django.conf import settings
from django.db import models

from apps.artworks.models import Artwork


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    artwork = models.ForeignKey(Artwork, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "مفضلة"
        verbose_name_plural = "المفضلة"
        constraints = [models.UniqueConstraint(fields=["user", "artwork"], name="favorite_unique_per_user")]
        indexes = [models.Index(fields=["user", "-created_at"], name="favorite_user_recent_idx")]

    def __str__(self) -> str:
        return f"{self.user_id} ♥ {self.artwork_id}"
