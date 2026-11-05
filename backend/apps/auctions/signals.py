from django.dispatch import receiver

from apps.orders.models import Order
from apps.orders.signals import order_status_changed

from . import services


@receiver(order_status_changed, sender=Order, dispatch_uid="auctions-award-on-deposit")
def _award_on_deposit(sender, order, to_status, **kwargs):
    services.on_order_status_changed(order, to_status)
