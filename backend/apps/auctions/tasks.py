from celery import shared_task

from . import services


@shared_task(queue="critical", ignore_result=True)
def auction_tick() -> int:
    return services.tick()
