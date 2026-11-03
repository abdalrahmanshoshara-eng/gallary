"""
Root URL configuration.

Django serves only the versioned API and the internal admin; every public page is served
by Next.js. nginx routes /api/ and the admin path here, /ws/ to the realtime process.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView

from apps.core.exceptions import api_not_found

api_v1 = [
    path("", include("apps.core.urls")),
    path("schema/", SpectacularAPIView.as_view(api_version="v1"), name="schema"),
]

urlpatterns = [
    path("api/v1/", include((api_v1, "v1"))),
    path(settings.DJANGO_ADMIN_PATH, admin.site.urls),
    # Must stay last: unknown API paths return the JSON error envelope, even with DEBUG on.
    re_path(r"^api/(?P<path>.*)$", api_not_found),
]

handler404 = "apps.core.exceptions.handler404"
handler500 = "apps.core.exceptions.handler500"
