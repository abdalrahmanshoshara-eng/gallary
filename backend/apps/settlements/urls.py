from django.urls import path

from .api import views

admin_urls = [
    path("settlements", views.SettlementListView.as_view(), name="settlements"),
    path("settlements/summary", views.SettlementSummaryView.as_view(), name="settlements-summary"),
    path("settlements/payees", views.SettlementPayeesView.as_view(), name="settlements-payees"),
    path("settlements/pay", views.SettlementPayView.as_view(), name="settlements-pay"),
    path("settlements/<uuid:public_id>/hold", views.SettlementHoldView.as_view(), name="settlement-hold"),
    path("settlements/<uuid:public_id>/release", views.SettlementReleaseView.as_view(), name="settlement-release"),
    path("settlements/<uuid:public_id>/cancel", views.SettlementCancelView.as_view(), name="settlement-cancel"),
]
