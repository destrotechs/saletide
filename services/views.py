from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
import logging
from django.utils.timezone import now
from datetime import timedelta,datetime
from .models import Service, ServiceProductRequirement,ItemType
from .serializers import (
    ServiceSerializer,
    ServiceProductRequirementSerializer,
    # AppointmentSerializer,
    ItemTypeSerializer
)
from django.utils import timezone

from companies.models import Company, Employee
from inventory.models import InventoryItem

logger = logging.getLogger("csm")


class ItemTypeViewSet(viewsets.ModelViewSet):
    """
    API for managing item types within a company.
    """
    serializer_class = ItemTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return item types belonging to the user's company.
        SuperAdmin can view all item types.
        Exclude soft-deleted items.
        """
        print("coming.....")
        user = self.request.user
        queryset = ItemType.objects.filter(deleted=False)  # Exclude deleted items

        if user.role == "SuperAdmin":
            return queryset  # SuperAdmin can view all items

        return queryset.filter(company=user.company)

    def create(self, request, *args, **kwargs):
        """
        Create an ItemType for the company.
        """
        user = request.user
        data = request.data.copy()

        if user.role == "SuperAdmin":
            # Ensure SuperAdmin provides a valid company ID
            if "company" not in data:
                return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            company = get_object_or_404(Company, id=data["company"])
        else:
            if user.role not in {"CompanyOwner", "CompanyAdmin"}:
                raise PermissionDenied("You are not authorized to create item types.")

            # Ensure the user is adding to their own company
            if str(user.company.id) != str(data.get("company")):
                raise PermissionDenied("You can only add item types to your own company.")

            company = user.company

        data["company"] = company.id  # Assign correct company
        serializer = self.get_serializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete an ItemType.
        Instead of deleting, it marks the record as deleted and updates `deleted_at`.
        """
        item_type = self.get_object()
        user = request.user
        if user.role not in {"SuperAdmin", "CompanyOwner","CompanyAdmin"}:
            raise PermissionDenied("You are not authorized to delete this item type.")

        # Ensure the user belongs to the company of the item type they want to delete
        if item_type.company != user.company and user.role != "SuperAdmin":
            raise PermissionDenied("You can only delete item types from your own company.")

        item_type.deleted = True
        item_type.deleted_at = timezone.now()
        item_type.save()

        return Response({"message": "ItemType marked as deleted."}, status=status.HTTP_200_OK)
class ServiceViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SuperAdmin":
            return Service.objects.filter(deleted=False)
        return Service.objects.filter(company=user.company, deleted=False)

    def create(self, request, *args, **kwargs):
        user = request.user
        data = request.data.copy()
        print("User Company",user.company.id)
        print("Request data",request.data)
        if user.role == "SuperAdmin":
            company_id = data.get("company")
            if not company_id:
                return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
            company = get_object_or_404(Company, id=company_id)
        elif 'company' in request.data and user.company.id!=request.data.get('company'):
            return  Response({"error":"You are not authorized to create a service in this company"},status=400)
        else:
            if user.role not in {"CompanyOwner", "CompanyAdmin"}:
                return Response({"error": "You are not authorized to create a service."}, status=status.HTTP_403_FORBIDDEN)
            company = user.company

        data["company"] = company.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    def destroy(self, request, *args, **kwargs):
        """
        Prevent deletion if:
        - The user is not authorized (not SuperAdmin, CompanyOwner, or CompanyAdmin).
        - The service belongs to a different company than the user.
        - The service has related appointments or product requirements.
        """
        # Get the service object
        service = self.get_object()
        user = request.user

        # Check if the user is a SuperAdmin or belongs to the same company as the service
        if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
            return Response({"error": "You are not authorized to delete this service."},
                            status=status.HTTP_403_FORBIDDEN)

        if service.company != user.company:  # Check if service belongs to user's company
            return Response({"error": "You are not authorized to delete this service."},
                             status=status.HTTP_403_FORBIDDEN)

        # Ensure there are no related appointments or product requirements
        if service.appointment_set.exists():
            return Response({"error": "Cannot delete service with existing appointments"},
                             status=status.HTTP_400_BAD_REQUEST)

        # Delete the service
        service.deleted = True
        service.deleted_at = timezone.now()
        service.save()
        return Response({"message": "Service deleted successfully"}, status=200)


class ServiceProductRequirementViewSet(viewsets.ModelViewSet):
    """
    API for managing service product requirements.
    """
    serializer_class = ServiceProductRequirementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ServiceProductRequirement.objects.filter(service__company=self.request.user.company)

        service_id = self.request.query_params.get('service', None)
        if service_id:
            queryset = queryset.filter(service_id=service_id)

        inventory_item_id = self.request.query_params.get('inventory_item', None)
        if inventory_item_id:
            queryset = queryset.filter(inventory_item_id=inventory_item_id)

        return queryset

    def create(self, request, *args, **kwargs):
        user = request.user

        # Ensure only authorized users can create product requirements
        if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
            return Response({"error": "You are not authorized to add product requirements."},
                            status=status.HTTP_403_FORBIDDEN)

        # Copy the request data
        data = request.data.copy()

        # Get the service and validate it belongs to the user's company
        service = get_object_or_404(Service, id=data.get("service"), company=user.company, deleted=False)

        if not service.requires_products:
            return Response({"error": "The requested service does not require a product."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Extract the inventory items list from the request data
        inventory_items = data.get("inventory_items", [])

        # Ensure the inventory_items list is not empty
        if not inventory_items:
            return Response({"error": "At least one inventory item is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        created_requirements = []

        for item_data in inventory_items:
            inventory_item = get_object_or_404(InventoryItem, id=item_data.get("id"), company=user.company,
                                               is_deleted=False)

            # Ensure that the service and inventory item belong to the same company
            if service.company != inventory_item.company:
                return Response({"error": "Service and InventoryItem must belong to the same company."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Create and validate product requirement for each item
            requirement_data = {
                "service": service.id,
                "inventory_item": inventory_item.id,
                "quantity_required": item_data.get("quantity_required")
            }

            serializer = self.get_serializer(data=requirement_data)

            if serializer.is_valid():
                created_requirement = serializer.save()
                created_requirements.append(created_requirement)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Return the created product requirements
        return Response(self.get_serializer(created_requirements, many=True).data,
                        status=status.HTTP_201_CREATED)


from django.utils.timezone import now

# class AppointmentViewSet(viewsets.ModelViewSet):
#     """
#     API for managing customer appointments.
#     """
#     serializer_class = AppointmentSerializer
#     permission_classes = [IsAuthenticated]
#
#     def get_queryset(self):
#         return Appointment.objects.filter(company=self.request.user.company)
#
#     def create(self, request, *args, **kwargs):
#         """
#         Create an appointment, ensuring the date_time is at least 1 hour later than the current time.
#         """
#         user = request.user
#         if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin", "CompanyManager"}:
#             return Response({"error": "You are not authorized to create appointments."}, status=status.HTTP_403_FORBIDDEN)
#
#         data = request.data.copy()
#         company = user.company
#
#         # Validate date_time
#         appointment_datetime = data.get("date_time")
#         if not appointment_datetime:
#             return Response({"error": "Appointment date and time are required."}, status=status.HTTP_400_BAD_REQUEST)
#
#         try:
#             appointment_datetime = datetime.fromisoformat(appointment_datetime)
#         except ValueError:
#             return Response({"error": "Invalid date format. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SS)."},
#                             status=status.HTTP_400_BAD_REQUEST)
#
#         # Ensure the appointment is at least 1 hour ahead of the current time
#         if appointment_datetime < now() + timedelta(hours=1):
#             return Response({"error": "Appointment must be scheduled at least 1 hour in the future."},
#                             status=status.HTTP_400_BAD_REQUEST)
#
#         # Validate foreign keys
#         service = get_object_or_404(Service, id=data.get("service"), company=company)
#
#         employee_id = data.get("employee")
#         employee = None
#         if employee_id:
#             employee = get_object_or_404(Employee, id=employee_id, company=company)
#
#         data["company"] = company.id
#         serializer = self.get_serializer(data=data)
#
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#     @action(detail=True, methods=["patch"])
#     def complete(self, request, pk=None):
#         """
#         Mark an appointment as completed.
#         """
#         appointment = self.get_object()
#         user = request.user
#
#         if user.role not in {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}:
#             return Response({"error": "You are not authorized to complete this appointment."}, status=status.HTTP_403_FORBIDDEN)
#
#         appointment.status = "Completed"
#         appointment.save()
#
#         return Response({"message": "Appointment marked as completed"}, status=status.HTTP_200_OK)
#

