from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCustomer
from apps.listings.models import Listing

from .. import services
from ..models import CartItem
from .serializers import AddToCartSerializer, CartCountSerializer, CartSerializer, QuantitySerializer, cart_payload


class CartView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(operation_id="cart_get", responses=CartSerializer)
    def get(self, request: Request) -> Response:
        return Response(cart_payload(request.user))


class CartCountView(APIView):
    """Header badge; cheap and cache-free."""

    permission_classes = [IsCustomer]

    @extend_schema(operation_id="cart_count", responses=CartCountSerializer)
    def get(self, request: Request) -> Response:
        return Response({"count": services.count(request.user)})


class CartItemsView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(operation_id="cart_add", request=AddToCartSerializer, responses={201: CartSerializer})
    def post(self, request: Request) -> Response:
        data = AddToCartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        listing = get_object_or_404(
            Listing.objects.select_related("artwork", "artwork__artist"), public_id=data.validated_data["listing"]
        )
        services.add_item(request.user, listing=listing, quantity=data.validated_data["quantity"])
        return Response(cart_payload(request.user), status=status.HTTP_201_CREATED)


def _line(request: Request, public_id) -> CartItem:
    # Scoped to the requester's cart: another user's line is simply "not found" (IDOR).
    return get_object_or_404(
        CartItem.objects.select_related("listing", "listing__artwork", "listing__artwork__artist"),
        public_id=public_id,
        cart__user=request.user,
    )


class CartItemDetailView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(operation_id="cart_update", request=QuantitySerializer, responses=CartSerializer)
    def patch(self, request: Request, public_id: str) -> Response:
        data = QuantitySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.update_quantity(_line(request, public_id), data.validated_data["quantity"])
        return Response(cart_payload(request.user))

    @extend_schema(operation_id="cart_remove", responses=CartSerializer)
    def delete(self, request: Request, public_id: str) -> Response:
        services.remove_item(_line(request, public_id))
        return Response(cart_payload(request.user))


class CartAcceptPricesView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(operation_id="cart_accept_prices", request=None, responses=CartSerializer)
    def post(self, request: Request) -> Response:
        services.accept_current_prices(request.user)
        return Response(cart_payload(request.user))
