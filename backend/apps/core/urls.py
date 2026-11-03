from django.urls import path

from .api.health import LivenessView, ReadinessView

app_name = "core"

urlpatterns = [
    path("health/live", LivenessView.as_view(), name="health-live"),
    path("health/ready", ReadinessView.as_view(), name="health-ready"),
]
