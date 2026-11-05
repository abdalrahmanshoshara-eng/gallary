"""Server-side cart: one per customer, fixed-price offers only, never reserves stock (BR-321…328)."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.listings.models import Listing


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"cart:{self.user_id}"


class CartItem(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveSmallIntegerField(default=1)
    # The price the customer saw; checkout refuses if the current price differs (BR-326).
    price_at_add = models.DecimalField(max_digits=12, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "listing"], name="cart_item_unique_listing"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="cart_item_quantity_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.cart_id}:{self.listing_id}×{self.quantity}"
