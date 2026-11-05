from django.urls import path

from .api import views

urls = [
    path("auctions", views.AuctionListView.as_view(), name="auctions"),
    path("auctions/<uuid:public_id>", views.AuctionDetailView.as_view(), name="auction-detail"),
    path("auctions/<uuid:public_id>/state", views.AuctionStateView.as_view(), name="auction-state"),
    path("auctions/<uuid:public_id>/bids", views.BidView.as_view(), name="auction-bid"),
    path("me/bids", views.MyBidsView.as_view(), name="my-bids"),
    path("auction-requests", views.MyAuctionRequestsView.as_view(), name="auction-requests"),
    path("auction-requests/<uuid:public_id>", views.MyAuctionRequestView.as_view(), name="auction-request"),
    path(
        "auction-requests/<uuid:public_id>/withdraw",
        views.MyAuctionRequestWithdrawView.as_view(),
        name="auction-request-withdraw",
    ),
]

admin_urls = [
    path("auctions", views.AdminAuctionListView.as_view(), name="auctions"),
    path("auctions/eligible-artworks", views.AdminEligibleArtworksView.as_view(), name="auction-eligible-artworks"),
    path("auctions/<uuid:public_id>", views.AdminAuctionDetailView.as_view(), name="auction-detail"),
    path("auctions/<uuid:public_id>/schedule", views.AdminAuctionScheduleView.as_view(), name="auction-schedule"),
    path("auctions/<uuid:public_id>/cancel", views.AdminAuctionCancelView.as_view(), name="auction-cancel"),
    path("auction-requests", views.AdminAuctionRequestListView.as_view(), name="auction-requests"),
    path("auction-requests/<uuid:public_id>", views.AdminAuctionRequestDetailView.as_view(), name="auction-request"),
    path(
        "auction-requests/<uuid:public_id>/transition",
        views.AdminAuctionRequestTransitionView.as_view(),
        name="auction-request-transition",
    ),
    path(
        "auction-requests/<uuid:public_id>/notes",
        views.AdminAuctionRequestNoteView.as_view(),
        name="auction-request-note",
    ),
    path(
        "auction-requests/<uuid:public_id>/commission",
        views.AdminAuctionRequestCommissionView.as_view(),
        name="auction-request-commission",
    ),
    path(
        "auction-requests/<uuid:public_id>/artwork",
        views.AdminAuctionRequestArtworkView.as_view(),
        name="auction-request-artwork",
    ),
]
