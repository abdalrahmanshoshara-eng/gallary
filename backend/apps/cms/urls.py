from django.urls import path

from .api import views

public_urls = [
    path("pages", views.PublicPagesView.as_view(), name="pages"),
    path("pages/<str:slug>", views.PublicPageView.as_view(), name="page"),
    path("faq", views.PublicFaqView.as_view(), name="faq"),
    path("home", views.HomeView.as_view(), name="home"),
]

admin_urls = [
    path("content/pages", views.AdminPagesView.as_view(), name="content-pages"),
    path("content/pages/<str:slug>", views.AdminPageView.as_view(), name="content-page"),
    path("content/pages/<str:slug>/publish", views.AdminPagePublishView.as_view(), name="content-page-publish"),
    path(
        "content/pages/<str:slug>/versions/<int:number>",
        views.AdminPageVersionView.as_view(),
        name="content-page-version",
    ),
    path("content/faq", views.AdminFaqListView.as_view(), name="content-faq"),
    path("content/faq/<uuid:public_id>", views.AdminFaqItemView.as_view(), name="content-faq-item"),
    path("content/faq/<uuid:public_id>/move", views.AdminFaqMoveView.as_view(), name="content-faq-move"),
    path("content/banners", views.AdminBannerListView.as_view(), name="content-banners"),
    path("content/banners/<uuid:public_id>", views.AdminBannerView.as_view(), name="content-banner"),
    path("content/banners/<uuid:public_id>/move", views.AdminBannerMoveView.as_view(), name="content-banner-move"),
    path("content/featured", views.AdminFeaturedListView.as_view(), name="content-featured"),
    path("content/featured/<uuid:artwork_id>", views.AdminFeaturedItemView.as_view(), name="content-featured-item"),
    path(
        "content/featured/<uuid:artwork_id>/move", views.AdminFeaturedMoveView.as_view(), name="content-featured-move"
    ),
]
