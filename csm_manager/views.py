from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from companies.models import Company

@api_view(['POST'])
@permission_classes([IsAdminUser])
def reset_admin_access(request, company_id):
    company = Company.objects.get(id=company_id)
    company.owner.set_password("newpassword123")
    company.owner.save()
    return Response({"message": "Admin access reset successfully"})
