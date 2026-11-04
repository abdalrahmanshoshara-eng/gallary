from django.urls import path

from .api import views

public_urls = [
    path("artworks", views.StorefrontListView.as_view(), name="artworks"),
    path("artworks/<str:slug>", views.StorefrontDetailView.as_view(), name="artwork-detail"),
]

admin_urls = [
    path("artworks/<uuid:public_id>/listings", views.AdminArtworkListingsView.as_view(), name="artwork-listings"),
    path("listings/<uuid:public_id>", views.AdminListingDetailView.as_view(), name="listing-detail"),
    path("listings/<uuid:public_id>/pricing", views.AdminListingPricingView.as_view(), name="listing-pricing"),
    path("listings/<uuid:public_id>/activate", views.AdminListingActivateView.as_view(), name="listing-activate"),
    path("listings/<uuid:public_id>/withdraw", views.AdminListingWithdrawView.as_view(), name="listing-withdraw"),
    path("settings", views.AdminSiteSettingView.as_view(), name="settings"),
]
