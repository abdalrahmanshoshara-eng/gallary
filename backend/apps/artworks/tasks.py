from celery import shared_task
from django.db.models import Q

from .models import Artwork


@shared_task(queue="default", ignore_result=True)
def refresh_search_text_task(relation: str, pk: int) -> int:
    from . import services

    condition = Q(**{relation: pk})
    if relation == "category":
        condition |= Q(category__parent=pk)  # parent names are indexed too
    return services.refresh_search_text_for(Artwork.objects.filter(condition).distinct())
