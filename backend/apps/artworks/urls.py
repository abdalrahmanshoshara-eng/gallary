from django.urls import path

from .api import views

public_urls = [
    path("archive", views.PublicArchiveListView.as_view(), name="archive"),
]

admin_urls = [
    path("artworks", views.AdminArtworkListView.as_view(), name="artworks"),
    path("artworks/<uuid:public_id>", views.AdminArtworkDetailView.as_view(), name="artwork-detail"),
    path("artworks/<uuid:public_id>/publish", views.AdminArtworkPublishView.as_view(), name="artwork-publish"),
    path("artworks/<uuid:public_id>/hide", views.AdminArtworkHideView.as_view(), name="artwork-hide"),
    path("artworks/<uuid:public_id>/archive", views.AdminArtworkArchiveView.as_view(), name="artwork-archive"),
    path("artworks/<uuid:public_id>/unarchive", views.AdminArtworkUnarchiveView.as_view(), name="artwork-unarchive"),
    path("artworks/<uuid:public_id>/images", views.AdminArtworkImagesView.as_view(), name="artwork-images"),
    path(
        "artworks/<uuid:public_id>/images/order",
        views.AdminArtworkImageOrderView.as_view(),
        name="artwork-images-order",
    ),
    path(
        "artworks/<uuid:public_id>/images/<uuid:image_id>",
        views.AdminArtworkImageDetailView.as_view(),
        name="artwork-image-detail",
    ),
]
