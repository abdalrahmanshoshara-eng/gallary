from celery import shared_task

from . import services


@shared_task(queue="critical", ignore_result=True)
def auction_tick() -> int:
    return services.tick()


@shared_task(ignore_result=True)
def notify_ending_soon() -> int:
    return services.notify_ending_soon()
