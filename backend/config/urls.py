"""
Root URL configuration.

Django serves only the versioned API and the internal admin; every public page is served
by Next.js. nginx routes /api/ and the admin path here, /ws/ to the realtime process.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView

from apps.accounts.urls import admin_urls as accounts_admin_urls
from apps.accounts.urls import auth_urls
from apps.artists import urls as artists_urls
from apps.artworks import urls as artworks_urls
from apps.auctions import urls as auctions_urls
from apps.audit import urls as audit_urls
from apps.cart import urls as cart_urls
from apps.catalog import urls as catalog_urls
from apps.cms import urls as cms_urls
from apps.core.exceptions import api_not_found
from apps.dashboard import urls as dashboard_urls
from apps.favorites import urls as favorites_urls
from apps.listings import urls as listings_urls
from apps.orders import urls as orders_urls
from apps.settlements import urls as settlements_urls

admin_v1 = [
    *accounts_admin_urls,
    *catalog_urls.admin_urls,
    *artists_urls.admin_urls,
    *artworks_urls.admin_urls,
    *listings_urls.admin_urls,
    *orders_urls.admin_urls,
    *auctions_urls.admin_urls,
    *settlements_urls.admin_urls,
    *dashboard_urls.admin_urls,
    *audit_urls.admin_urls,
    *cms_urls.admin_urls,
]
public_v1 = [
    *catalog_urls.public_urls,
    *artists_urls.public_urls,
    *listings_urls.public_urls,  # storefront: artworks list/detail with offers and search
    *artworks_urls.public_urls,
    *favorites_urls.urls,
    *cart_urls.urls,
    *orders_urls.urls,
    *auctions_urls.urls,
    *cms_urls.public_urls,
]

api_v1 = [
    path("", include("apps.core.urls")),
    path("auth/", include((auth_urls, "auth"))),
    path("admin/", include((admin_v1, "admin"))),
    path("", include((public_v1, "public"))),
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
