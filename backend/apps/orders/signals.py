"""Order lifecycle signals for features built on top of orders (auctions), so that orders
never import them. Sent inside the transaction that changes the status."""

from django.dispatch import Signal

# kwargs: order, from_status, to_status, actor
order_status_changed = Signal()
