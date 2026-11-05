from celery import shared_task

from . import services


@shared_task(queue="critical", ignore_result=True)
def expire_due_orders() -> int:
    return services.expire_due_orders()
