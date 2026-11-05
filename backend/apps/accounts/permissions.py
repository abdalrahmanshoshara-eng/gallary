from rest_framework.permissions import BasePermission

from .roles import is_super_admin


class IsSuperAdmin(BasePermission):
    message = "هذه العملية متاحة للمدير العام فقط."

    def has_permission(self, request, view) -> bool:
        return is_super_admin(request.user)


class IsCatalogEditor(BasePermission):
    """Content staff and Super Admin manage artists, artworks and classifications (PRD §8)."""

    message = "هذه العملية متاحة لموظفي المحتوى والمدير العام فقط."

    def has_permission(self, request, view) -> bool:
        from .roles import Role, has_any_role

        user = request.user
        return bool(
            getattr(user, "is_authenticated", False)
            and user.is_active
            and user.is_staff
            and has_any_role(user, [Role.CONTENT_STAFF, Role.SUPER_ADMIN])
        )


class IsCustomer(BasePermission):
    """Cart, orders and favourites-to-buy are for customer accounts only (PRD §8)."""

    message = "الشراء متاح لحسابات العملاء فقط."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(getattr(user, "is_authenticated", False) and user.is_active and not user.is_staff)


class IsOrdersStaff(BasePermission):
    """Operations staff and Super Admin manage orders, payments and delivery (PRD §8)."""

    message = "هذه العملية متاحة لموظفي العمليات والمدير العام فقط."

    def has_permission(self, request, view) -> bool:
        from .roles import Role, has_any_role

        user = request.user
        return bool(
            getattr(user, "is_authenticated", False)
            and user.is_active
            and user.is_staff
            and has_any_role(user, [Role.OPERATIONS_STAFF, Role.SUPER_ADMIN])
        )
