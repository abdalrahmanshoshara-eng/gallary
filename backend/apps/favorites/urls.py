from django.urls import path

from .api import views

urls = [
    path("favorites", views.FavoriteListView.as_view(), name="favorites"),
    path("favorites/ids", views.FavoriteIdsView.as_view(), name="favorite-ids"),
    path("favorites/<uuid:artwork_id>", views.FavoriteDetailView.as_view(), name="favorite-detail"),
]
