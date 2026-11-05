from django.urls import path

from .api import views

urls = [
    path("orders/policy", views.PolicyView.as_view(), name="orders-policy"),
    path("orders/checkout", views.CheckoutView.as_view(), name="orders-checkout"),
    path("orders", views.MyOrdersView.as_view(), name="orders"),
    path("orders/<str:number>", views.MyOrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:number>/cancel", views.MyOrderCancelView.as_view(), name="order-cancel"),
]

admin_urls = [
    path("orders", views.AdminOrderListView.as_view(), name="orders"),
    path("orders/<str:number>", views.AdminOrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:number>/payments", views.AdminPaymentsView.as_view(), name="order-payments"),
    path(
        "orders/<str:number>/payments/<uuid:payment_id>/confirm",
        views.AdminPaymentConfirmView.as_view(),
        name="order-payment-confirm",
    ),
    path(
        "orders/<str:number>/payments/<uuid:payment_id>/void",
        views.AdminPaymentVoidView.as_view(),
        name="order-payment-void",
    ),
    path(
        "orders/<str:number>/items/<uuid:item_id>/remove",
        views.AdminOrderItemRemoveView.as_view(),
        name="order-item-remove",
    ),
    path("orders/<str:number>/deposit", views.AdminOrderDepositView.as_view(), name="order-deposit"),
    path("orders/<str:number>/cancel", views.AdminOrderCancelView.as_view(), name="order-cancel"),
    path("orders/<str:number>/delivery", views.AdminOrderDeliveryView.as_view(), name="order-delivery"),
    path("orders/<str:number>/complete", views.AdminOrderCompleteView.as_view(), name="order-complete"),
]
