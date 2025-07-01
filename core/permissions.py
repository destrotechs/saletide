from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from .models import Role

class IsSuperAdmin(BasePermission):
    """
    Custom permission to only allow SuperAdmin users.
    """
    def has_permission(self, request, view):
        return request.user.role == Role.SUPER_ADMIN


class IsCompanyOwnerOrAdmin(BasePermission):
    """
    Custom permission to only allow Owner and Admin users to access certain views.
    """
    def has_permission(self, request, view):
        return request.user.role in [Role.COMPANY_OWNER, Role.COMPANY_ADMIN]


class IsCompanyManager(BasePermission):
    """
    Custom permission to allow only Managers to access specific resources.
    """
    def has_permission(self, request, view):
        return request.user.role == Role.COMPANY_MANAGER
class IsCompanyOwner(BasePermission):
    """
    Custom permission to only allow Owner and Admin users to access certain views.
    """
    def has_permission(self, request, view):
        return request.user.role in [Role.COMPANY_OWNER]
class IsCompanyActive(BasePermission):
    """
    Permission to ensure the user's company is active/subscribed.
    """

    def has_permission(self, request, view):
        user = request.user

        # Skip check if user is not authenticated (e.g., AllowAny views)
        if not user or not user.is_authenticated:
            return False

        # Allow superusers or users with no company (optional)
        if getattr(user, 'is_superuser', False):
            return True

        company = getattr(user, 'company', None)

        if company and not company.is_active:
            raise PermissionDenied("Your company subscription is inactive. Please contact support.")

        return True