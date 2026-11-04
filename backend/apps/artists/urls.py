from django.urls import path

from .api import views

public_urls = [
    path("artists", views.PublicArtistListView.as_view(), name="artists"),
    path("artists/<str:slug>", views.PublicArtistDetailView.as_view(), name="artist-detail"),
]

admin_urls = [
    path("artists", views.AdminArtistListView.as_view(), name="artists"),
    path("artists/<uuid:public_id>", views.AdminArtistDetailView.as_view(), name="artist-detail"),
    path("artists/<uuid:public_id>/photo", views.AdminArtistPhotoView.as_view(), name="artist-photo"),
]
