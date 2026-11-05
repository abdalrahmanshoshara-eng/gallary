from django.urls import path

from .api import views

urls = [
    path("cart", views.CartView.as_view(), name="cart"),
    path("cart/count", views.CartCountView.as_view(), name="cart-count"),
    path("cart/items", views.CartItemsView.as_view(), name="cart-items"),
    path("cart/items/<uuid:public_id>", views.CartItemDetailView.as_view(), name="cart-item"),
    path("cart/accept-prices", views.CartAcceptPricesView.as_view(), name="cart-accept-prices"),
]
