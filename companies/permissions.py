from rest_framework.permissions import BasePermission
from core.models import Role
class IsCSMSuperAdmin(BasePermission):
    """Allows only the CSM Super Admin to create companies."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff

class IsDirector(BasePermission):
    """Allows only company directors to modify their own company."""
    def has_permission(self, request, view):
        return request.user.role in [Role.COMPANY_OWNER, Role.COMPANY_ADMIN]