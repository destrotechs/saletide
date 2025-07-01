from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.status import HTTP_403_FORBIDDEN
from django.template.loader import render_to_string
from weasyprint import HTML
from django.http import HttpResponse
from companies.models import Company
from .models import InventoryCategory, InventoryItem
from .serializers import InventoryCategorySerializer, InventoryItemSerializer
import os
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils.timezone import now
from rest_framework.response import Response
from django.utils.dateparse import parse_date
class InventoryCategoryViewSet(viewsets.ModelViewSet):
    """
    API for managing inventory categories.
    """
    serializer_class = InventoryCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return categories for the company of the logged-in user
        return InventoryCategory.objects.filter(company=self.request.user.company,is_deleted=False)

    def create(self, request, *args, **kwargs):
        user = request.user

        # Only allow authorized roles
        if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
            return Response({"error": "You are not authorized to create categories."},
                            status=status.HTTP_403_FORBIDDEN)

        # Ensure the user's company is active and not deleted
        company = get_object_or_404(Company, id=user.company.id, is_deleted=False)

        # Copy data and force the company ID
        data = request.data.copy()
        data['company'] = company.id

        # Replace request.data with the updated data
        request._full_data = data  # Note: This is a bit of a workaround for DRF internals

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        user = request.user
        # Ensure only authorized users can update inventory categories for their company
        if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
            return Response({"error": "You are not authorized to update categories."}, status=status.HTTP_403_FORBIDDEN)

        # Ensure the category belongs to the user's company
        category = self.get_object()
        if category.company != user.company:
            return Response({"error": "You can only update categories for your company."}, status=status.HTTP_403_FORBIDDEN)

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = request.user
        # Ensure only authorized users can delete inventory categories for their company
        if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
            return Response({"error": "You are not authorized to delete categories."}, status=status.HTTP_403_FORBIDDEN)

        # Ensure the category belongs to the user's company
        category = self.get_object()
        if category.company != user.company:
            return Response({"error": "You can only delete categories for your company."}, status=status.HTTP_403_FORBIDDEN)

        category.is_deleted = True
        category.deleted_at = timezone.now()  # Soft delete the category
        category.save()
        return Response({"message": "Category deleted successfully."}, status=status.HTTP_200_OK)


class InventoryItemViewSet(viewsets.ModelViewSet):
    """
    API for managing inventory items.
    """
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Return only inventory items for the company of the logged-in user
        return InventoryItem.objects.filter(company=self.request.user.company, is_deleted=False)

    def create(self, request, *args, **kwargs):
        user = request.user
        # Ensure only authorized users can create inventory items for their company
        if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
            return Response({"error": "You are not authorized to create inventory items."}, status=status.HTTP_403_FORBIDDEN)

        # Make sure the inventory item is created for the user's company
        data = request.data.copy()

        data['company'] = user.company.id  # Ensure the item is created for the user's company

        # Create the inventory item
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    from rest_framework import status
    from rest_framework.response import Response

    def update(self, request, *args, **kwargs):
        user = request.user

        # Check role authorization
        if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
            return Response({"error": "You are not authorized to update inventory items."},
                            status=status.HTTP_403_FORBIDDEN)

        inventory_item = self.get_object()

        # Check company ownership
        if inventory_item.company != user.company:
            return Response({"error": "You can only update inventory items for your company."},
                            status=status.HTTP_403_FORBIDDEN)

        # Capture original quantity before update
        old_quantity = inventory_item.quantity

        # Deserialize and validate the incoming data
        serializer = self.get_serializer(inventory_item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Remove quantity from validated_data so serializer doesn't apply it directly
        quantity_change = serializer.validated_data.pop("quantity", None)

        # Save the other fields
        serializer.save()

        # Now handle quantity manually
        if quantity_change is not None:
            quantity_diff = quantity_change - old_quantity
            if quantity_diff > 0:
                inventory_item.increase_stock(quantity_diff, user=user, notes="Manual stock increase via API")
            elif quantity_diff < 0:
                inventory_item.reduce_stock(abs(quantity_diff), user=user, notes="Manual stock reduction via API")

        return Response({"message":"Stocks changed successfully","data":self.get_serializer(inventory_item).data},status=200)

    def destroy(self, request, *args, **kwargs):
        user = request.user
        # Ensure only authorized users can delete inventory items for their company
        if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
            return Response({"error": "You are not authorized to delete inventory items."}, status=status.HTTP_403_FORBIDDEN)

        # Ensure the inventory item belongs to the user's company
        inventory_item = self.get_object()
        if inventory_item.company != user.company:
            return Response({"error": "You can only delete inventory items for your company."}, status=status.HTTP_403_FORBIDDEN)

        # Ensure the item isn't already deleted
        if inventory_item.is_deleted:
            return Response({"error": "This inventory item is already deleted."}, status=status.HTTP_400_BAD_REQUEST)

        # Proceed with soft delete
        inventory_item.is_deleted = True
        inventory_item.deleted_at = timezone.now()  # Soft delete the item
        inventory_item.save()
        return Response({"message": "Inventory item marked as deleted."}, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        user = request.user
        # Ensure only authorized users can partially update inventory items for their company
        if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
            return Response({"error": "You are not authorized to partially update inventory items."}, status=status.HTTP_403_FORBIDDEN)

        # Ensure the inventory item belongs to the user's company
        inventory_item = self.get_object()
        if inventory_item.company != user.company:
            return Response({"error": "You can only partially update inventory items for your company."}, status=status.HTTP_403_FORBIDDEN)

        return super().partial_update(request, *args, **kwargs)



    @action(detail=False, methods=['get'], url_path='generate-inventory-report')
    def generate_inventory_report(self, request):
        company = request.user.company

        # 1. Read date filters from query params
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        # Parse dates safely
        if start_date:
            start_date = parse_date(start_date)
        if end_date:
            end_date = parse_date(end_date)

        # 2. Get inventory items
        inventory_items = InventoryItem.objects.filter(
            company=company,
            is_deleted=False
        ).prefetch_related("transactions")

        # 3. Filter transactions inside template context (optional, depending on how you want to render)

        # 4. OR, filter transactions queryset manually and attach
        for item in inventory_items:
            transactions = item.transactions.all()
            if start_date:
                transactions = transactions.filter(timestamp__date__gte=start_date)
            if end_date:
                transactions = transactions.filter(timestamp__date__lte=end_date)
            item.filtered_transactions = transactions  # attach filtered transactions manually

        current_date = timezone.now()

        html_string = render_to_string("inventory-report.html", {
            "inventory_items": inventory_items,
            "company_name": company.name,
            "user": request.user,
            "current_date": current_date,
        })

        # 5. Generate PDF
        pdf_file = HTML(string=html_string).write_pdf()

        # 6. Save PDF
        filename = f"inventory_report_{now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = os.path.join("reports", filename)
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(pdf_file)

        # 7. Return report URL
        report_url = request.build_absolute_uri(settings.MEDIA_URL + file_path)

        return Response({"report_url": report_url})

