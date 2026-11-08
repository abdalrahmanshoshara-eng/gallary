from django.dispatch import receiver

from apps.orders.models import Order
from apps.orders.signals import order_status_changed

from . import services


@receiver(order_status_changed, sender=Order, dispatch_uid="settlements-on-order-status")
def _on_order_status(sender, order, from_status, to_status, **kwargs):
    services.on_order_status_changed(order, from_status, to_status)
