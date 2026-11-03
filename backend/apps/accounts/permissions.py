from rest_framework.permissions import BasePermission

from .roles import is_super_admin


class IsSuperAdmin(BasePermission):
    message = "هذه العملية متاحة للمدير العام فقط."

    def has_permission(self, request, view) -> bool:
        return is_super_admin(request.user)
