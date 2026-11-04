from django.urls import path

from .api import views

public_urls = [
    path("catalog/categories", views.PublicCategoriesView.as_view(), name="catalog-categories"),
    path("catalog/materials", views.PublicMaterialsView.as_view(), name="catalog-materials"),
    path("catalog/techniques", views.PublicTechniquesView.as_view(), name="catalog-techniques"),
]

admin_urls = []
for _kind in views.ADMIN_TERMS:
    _list, _detail = views._admin_term_views(_kind)
    admin_urls += [
        path(f"catalog/{_kind}", _list.as_view(), name=f"{_kind}"),
        path(f"catalog/{_kind}/<int:pk>", _detail.as_view(), name=f"{_kind}-detail"),
    ]
