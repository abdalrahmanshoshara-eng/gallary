from django.urls import path

from .api import views

admin_urls = [
    path("audit", views.AuditLogListView.as_view(), name="audit"),
    path("audit/facets", views.AuditFacetsView.as_view(), name="audit-facets"),
]
