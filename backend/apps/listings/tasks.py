from celery import shared_task

from . import services


@shared_task(queue="default", ignore_result=True)
def end_expired_listings() -> int:
    return services.end_expired_listings()
