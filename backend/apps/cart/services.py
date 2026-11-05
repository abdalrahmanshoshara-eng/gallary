"""
Cart operations (BR-321…328). Adding never reserves stock; the cart always shows current
price and availability, and checkout re-checks everything under locks.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction

from apps.core.errors import ConflictError
from apps.listings import services as listing_services
from apps.listings.models import Listing, QuantityMode, SaleMode

from .models import Cart, CartItem

MAX_ITEMS = 20  # BR-328


class CartFullError(ConflictError):
    code = "CART_FULL"
    message = f"العربة تتسع لـ {MAX_ITEMS} عنصراً كحد أقصى. أكمل طلبك أو احذف بعض العناصر."


class NotAddableError(ConflictError):
    code = "NOT_ADDABLE"
    message = "لا يمكن إضافة هذا العمل إلى العربة حالياً."


@dataclass
class LineState:
    item: CartItem
    problem: str | None
    price_changed: bool


def get_cart(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _items(cart: Cart):
    return cart.items.select_related(
        "listing", "listing__artwork", "listing__artwork__artist", "listing__artwork__category"
    ).prefetch_related("listing__artwork__images__asset")


def max_quantity(listing: Listing) -> int:
    """BR-324: unique → 1; limited → min(max_per_order, available); unlimited → max_per_order."""
    if listing.quantity_mode == QuantityMode.UNIQUE:
        return 1
    if listing.quantity_mode == QuantityMode.LIMITED:
        return max(0, min(listing.max_per_order, listing.quantity_available))
    return listing.max_per_order


def line_states(cart: Cart) -> list[LineState]:
    states = []
    for item in _items(cart):
        problem = listing_services.purchase_problem(item.listing, item.quantity)
        changed = item.listing.price_usd is not None and item.listing.price_usd != item.price_at_add
        states.append(LineState(item=item, problem=problem, price_changed=changed))
    return states


def _addable(listing: Listing, quantity: int) -> None:
    if listing.sale_mode != SaleMode.FIXED_PRICE:  # BR-322: auctions never enter the cart
        raise NotAddableError("أعمال المزاد لا تُضاف إلى العربة.", details={"reason": "auction_only"})
    problem = listing_services.purchase_problem(listing, quantity)
    if problem == "quantity_limit" or problem == "insufficient_stock":
        raise NotAddableError(
            "الكمية المطلوبة تتجاوز المتاح.", details={"reason": problem, "max_quantity": max_quantity(listing)}
        )
    if problem:
        raise NotAddableError(details={"reason": problem})


@transaction.atomic
def add_item(user, *, listing: Listing, quantity: int = 1) -> CartItem:
    """Adds a line, or sets the quantity of an existing line for the same offer."""
    cart = Cart.objects.select_for_update().get(pk=get_cart(user).pk)
    _addable(listing, quantity)
    item = cart.items.filter(listing=listing).first()
    if item is None:
        if cart.items.count() >= MAX_ITEMS:
            raise CartFullError()
        try:
            with transaction.atomic():
                item = CartItem.objects.create(
                    cart=cart, listing=listing, quantity=quantity, price_at_add=listing.price_usd
                )
        except IntegrityError:  # concurrent add of the same offer
            item = cart.items.get(listing=listing)
    item.quantity = quantity
    item.price_at_add = listing.price_usd
    item.save(update_fields=["quantity", "price_at_add"])
    cart.save(update_fields=["updated_at"])
    return item


@transaction.atomic
def update_quantity(item: CartItem, quantity: int) -> CartItem:
    listing = item.listing
    if quantity < 1:
        raise ConflictError("الكمية يجب أن تكون 1 على الأقل.", code="VALIDATION_ERROR", http_status=400)
    _addable(listing, quantity)
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    return item


def remove_item(item: CartItem) -> None:
    item.delete()


@transaction.atomic
def accept_current_prices(user) -> int:
    """The customer acknowledges price changes (BR-326): lines take the current prices."""
    changed = 0
    for state in line_states(get_cart(user)):
        if state.price_changed:
            state.item.price_at_add = state.item.listing.price_usd
            state.item.save(update_fields=["price_at_add"])
            changed += 1
    return changed


def count(user) -> int:
    return CartItem.objects.filter(cart__user=user).count()
