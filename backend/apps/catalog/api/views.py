from __future__ import annotations

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCatalogEditor

from .. import selectors, services
from ..models import Category, Material, Tag, Technique
from .serializers import (
    AdminCategorySerializer,
    AdminMaterialSerializer,
    AdminTagSerializer,
    AdminTechniqueSerializer,
    PublicCategorySerializer,
    PublicTermSerializer,
)


class PublicCategoriesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="catalog_categories", responses=PublicCategorySerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(PublicCategorySerializer(selectors.active_category_tree(), many=True).data)


def _public_terms_view(model, operation_id: str):
    class View(APIView):
        permission_classes = [AllowAny]

        @extend_schema(operation_id=operation_id, responses=PublicTermSerializer(many=True))
        def get(self, request: Request) -> Response:
            qs = model.objects.filter(is_active=True).order_by("sort_order", "name")
            return Response(PublicTermSerializer(qs, many=True).data)

    View.__name__ = f"Public{model.__name__}sView"
    return View


PublicMaterialsView = _public_terms_view(Material, "catalog_materials")
PublicTechniquesView = _public_terms_view(Technique, "catalog_techniques")


# --- staff ------------------------------------------------------------------------------
ADMIN_TERMS = {
    "categories": (Category, AdminCategorySerializer),
    "materials": (Material, AdminMaterialSerializer),
    "techniques": (Technique, AdminTechniqueSerializer),
    "tags": (Tag, AdminTagSerializer),
}


def _admin_term_views(kind: str):
    model, serializer_class = ADMIN_TERMS[kind]

    def annotated():
        qs = model.objects.annotate(usage_count=Count("artworks", distinct=True))
        if model is Category:
            qs = qs.select_related("parent")
        return qs.order_by("sort_order", "name")

    class ListCreate(APIView):
        permission_classes = [IsCatalogEditor]

        @extend_schema(operation_id=f"admin_{kind}_list", responses=serializer_class(many=True))
        def get(self, request: Request) -> Response:
            return Response(serializer_class(annotated(), many=True).data)

        @extend_schema(operation_id=f"admin_{kind}_create", request=serializer_class, responses={201: serializer_class})
        def post(self, request: Request) -> Response:
            data = serializer_class(data=request.data)
            data.is_valid(raise_exception=True)
            term = services.create_term(model, actor=request.user, data=dict(data.validated_data))
            return Response(serializer_class(annotated().get(pk=term.pk)).data, status=status.HTTP_201_CREATED)

    class Detail(APIView):
        permission_classes = [IsCatalogEditor]

        @extend_schema(operation_id=f"admin_{kind}_update", request=serializer_class, responses=serializer_class)
        def patch(self, request: Request, pk: int) -> Response:
            term = get_object_or_404(model, pk=pk)
            data = serializer_class(term, data=request.data, partial=True)
            data.is_valid(raise_exception=True)
            values = dict(data.validated_data)
            if values.get("slug") == "":
                values.pop("slug")
            services.update_term(term, actor=request.user, data=values)
            return Response(serializer_class(annotated().get(pk=term.pk)).data)

        @extend_schema(operation_id=f"admin_{kind}_delete", responses={204: None})
        def delete(self, request: Request, pk: int) -> Response:
            services.delete_term(get_object_or_404(model, pk=pk), actor=request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)

    ListCreate.__name__ = f"Admin{model.__name__}ListView"
    Detail.__name__ = f"Admin{model.__name__}DetailView"
    return ListCreate, Detail
