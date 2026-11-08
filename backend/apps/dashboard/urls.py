from django.urls import path

from .api import views

admin_urls = [path("dashboard", views.DashboardView.as_view(), name="dashboard")]
