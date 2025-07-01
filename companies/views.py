import decimal

from django.db.models import Sum
from django_extensions import models
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import (
    Company,
    Employee,
    EmployeeLeave,
    EmployeeRemuneration,
    EmployeeDeduction,
    EmployeeCommission,
    EmployeeCommissionSetting,
EmployeePayroll
)
from .serializers import (
    CompanySerializer,
    EmployeeSerializer,
    EmployeeCommissionSerializer,
    EmployeeRemunerationSerializer,
    EmployeeCommissionSettingSerializer,
    EmployeeDeductionSerializer,
    EmployeeLeaveSerializer, CompanyRegistrationSerializer
)
# from companies.permissions import IsCSMSuperAdmin, IsDirector
from core.permissions import IsCompanyOwnerOrAdmin, IsCompanyManager,IsSuperAdmin,IsCompanyOwner
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
import datetime
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.utils import timezone
from core.serializers import RegisterSerializer,UserSerializer
from core.models import Role
from django.conf import settings
import os
from django.template.loader import render_to_string
from weasyprint import HTML
from core.permissions import IsCompanyActive
User = get_user_model()
import logging

logger = logging.getLogger("csm")


from decimal import Decimal


def calculate_paye(taxable_income):
    """
    Enhanced PAYE calculation function with updated tax bands
    """
    if taxable_income <= 0:
        return Decimal('0')

    # Kenya PAYE tax bands (2024 rates)
    tax_bands = [
        (24000, Decimal('0.10')),  # 10% on first 24,000
        (8333, Decimal('0.25')),  # 25% on next 8,333 (24,001 - 32,333)
        (467667, Decimal('0.30')),  # 30% on next 467,667 (32,334 - 500,000)
        (300000, Decimal('0.325')),  # 32.5% on next 300,000 (500,001 - 800,000)
        (float('inf'), Decimal('0.35'))  # 35% on amount above 800,000
    ]

    total_tax = Decimal('0')
    remaining_income = taxable_income

    for band_limit, rate in tax_bands:
        if remaining_income <= 0:
            break

        taxable_in_band = min(remaining_income, Decimal(str(band_limit)))
        total_tax += taxable_in_band * rate
        remaining_income -= taxable_in_band

    # Personal relief deduction
    personal_relief = Decimal('2400')  # Monthly personal relief
    final_tax = max(total_tax - personal_relief, Decimal('0'))

    return final_tax.quantize(Decimal('0.01'))

class CompanyViewSet(viewsets.ModelViewSet):
    """
    View for managing companies. Only the CSM Super Admin can create companies.
    Directors can be added later.
    """
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated,IsCompanyActive]

    from django.core.exceptions import PermissionDenied

    def get_queryset(self):
        """
        Override queryset:
        - Super Admin gets all companies.
        - Regular users only see their company.
        - Handle case where user has no company with a clear error message.
        """
        user = self.request.user

        if user.role == "SuperAdmin":
            return Company.objects.all()  # SuperAdmin gets all companies

        if not user.company:
            raise PermissionDenied("You are not associated with any company. Please contact your administrator.")

        return Company.objects.filter(id=user.company.id,is_deleted=False)  # Regular user sees their own company only

    def update(self, request, *args, **kwargs):
        """
        Update company details.
        - Super Admin can update any company.
        - A company director can update their own company.
        """
        instance = self.get_object()
        user = request.user
        if instance.is_deleted:
            return Response({"error": "This company has been deleted and cannot be updated."},
                            status=status.HTTP_400_BAD_REQUEST)

        if user.role not in ["SuperAdmin","CompanyOwner"] and instance.id != user.company.id:
            logger.info("You are not authorized to update this company")
            return Response({"error": "You are not authorized to update this company."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, data=request.data, partial=False)  # Full update (PUT)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)


    def partial_update(self, request, *args, **kwargs):
        """
        Partially update a company (PATCH).
        - Super Admin can update any company.
        - A company director can update their own company.
        """
        instance = self.get_object()
        user = request.user
        if instance.is_deleted:
            return Response({"error": "This company has been deleted and cannot be updated."},
                            status=status.HTTP_400_BAD_REQUEST)

        if user.role not in ["SuperAdmin","CompanyOwner"] or instance.id != user.company.id:
            logger.info("You are not authorized to update this company")

            return Response({"error": "You are not authorized to update this company."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, data=request.data, partial=True)  # Partial update (PATCH)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve method:
        - Super Admin can access any company.
        - Regular users can only access their own company.
        """
        user = request.user
        company = self.get_object()
        if company.is_deleted:
            return Response({"error": "This company has been deleted."},
                            status=status.HTTP_400_BAD_REQUEST)

        if user.role != "SuperAdmin" and user.company != company:
            return Response({"error": "You are not allowed to view this company."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """
        Override delete:
        - Only Super Admin can soft delete a company.
        - Return custom response instead of default 204.
        """
        instance = self.get_object()

        if instance.is_deleted:
            return Response({"error": "This company has already been deleted."}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        if user.role != "SuperAdmin":
            logger.error("You are not authorized to delete this company")
            return Response({"error": "You do not have permission to delete this company."},
                            status=status.HTTP_403_FORBIDDEN)

        # Soft delete
        instance.is_deleted = True
        instance.date_deleted = timezone.now()
        instance.save()

        return Response({"message": "Company deleted successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsSuperAdmin])
    def register_company(self, request):
        """
        Register a new company. Only the CSM Super Admin can do this.
        """
        user = self.request.user
        if user.role != "SuperAdmin":
            logger.error("You are not authorized to register a company")
            return Response({"error": "You do not have permission to register a company."},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            company = serializer.save()

            return Response({
                "message": "Company registered successfully.",
                "company": CompanySerializer(company).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsSuperAdmin | IsCompanyOwnerOrAdmin])
    def add_director(self, request, pk=None):
        """
        Adds a director to a company. Only the CSM Super Admin or existing directors can add.
        """
        company = self.get_object()
        if company.is_deleted:
            return Response({"error": "This company has been deleted and cannot be updated."},
                            status=status.HTTP_400_BAD_REQUEST)
        email = request.data.get("email")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User with this email does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        company.directors.add(user)
        user.company = company
        user.save()
        return Response({"message": f"{user.email} added as a director."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsSuperAdmin | IsCompanyOwnerOrAdmin])
    def remove_director(self, request, pk=None):
        """
        Removes a director from a company.
        """
        company = self.get_object()
        if company.is_deleted:
            return Response({"error": "This company has been deleted and cannot be updated."},
                            status=status.HTTP_400_BAD_REQUEST)
        email = request.data.get("email")

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User with this email does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        if user not in company.directors.all():
            return Response({"error": "User is not a director of this company."}, status=status.HTTP_400_BAD_REQUEST)

        company.directors.remove(user)
        return Response({"message": f"{user.email} removed as a director."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="upload-logo")
    def upload_logo(self, request, pk=None):
        company = self.get_object()
        logo = request.FILES.get('company_logo')
        if logo:
            company.company_logo = logo
            company.save()
            return Response({"message": "Logo updated successfully"}, status=200)
        return Response({"detail": "No file uploaded"}, status=400)

class EmployeeViewSet(viewsets.ModelViewSet):
    """
    View for managing employees.
    - Only SuperAdmin, CompanyOwner, and CompanyAdmin can create, update, or delete employees.
    - Regular users can only view their own company's employees.
    """
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin | IsCompanyOwnerOrAdmin | IsCompanyManager,IsCompanyActive]

    def get_queryset(self):
        """
        - SuperAdmin can see all employees or filter by a specific company ID.
        - Regular users only see employees from their own company.
        """
        user = self.request.user
        company_id = self.kwargs.get("company_pk")

        print("Company ID ", company_id)

        if user.role == "SuperAdmin":
            if company_id:
                return Employee.objects.filter(company_id=company_id, is_deleted=False)
            return Employee.objects.filter(is_deleted=False)

        if not user.company:
            return Employee.objects.none()

        if company_id and user.company.id == int(company_id):
            return Employee.objects.filter(company_id=company_id, is_deleted=False)

        return Employee.objects.filter(company=user.company, is_deleted=False)

    def create(self, request, *args, **kwargs):
        """
        Create an employee and assign them to the specified company.
        - Only SuperAdmin, CompanyOwner, or CompanyAdmin can add employees.
        """
        user = request.user
        data = request.data.copy()
        company_id = self.kwargs.get("company_pk")

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        company = get_object_or_404(Company, id=company_id)
        if company.is_deleted:
            return Response({"error": "This company has been deleted."}, status=status.HTTP_400_BAD_REQUEST)

        allowed_roles = {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}
        if user.role not in allowed_roles:
            return Response({"error": "You are not authorized to add employees."}, status=status.HTTP_403_FORBIDDEN)

        if user.role != "SuperAdmin" and user.company != company:
            return Response({"error": "You are not authorized to add employees to this company."},
                            status=status.HTTP_403_FORBIDDEN)

        # --- Step 1: Create the user (employee) ---
        user_serializer = RegisterSerializer(data=data)
        if not user_serializer.is_valid():
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        employee_user = user_serializer.save()
        print("Created User:", employee_user)

        # --- Step 2: Create the Employee and assign to the company ---
        data["user_id"] = employee_user.id
        data['user'] = employee_user
        data["company"] = company_id

        employee_serializer = self.get_serializer(data=data)
        if employee_serializer.is_valid():
            employee_serializer.save()
            logger.info(f"Employee {employee_serializer.data['id']} added to company {company.name} by {user.email}")
            return Response({
                "message": f"Employee {employee_serializer.data['id']} added to company {company.name} by {user.email}",
                "data": employee_serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(employee_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_object(self):
        """
        Override get_object to ensure we fetch an employee from a specific company.
        """
        company_pk = self.kwargs.get("company_pk")
        employee_pk = self.kwargs.get("pk")  # This is the employee PK

        try:
            employee = Employee.objects.get(pk=employee_pk, company_id=company_pk)
        except Employee.DoesNotExist:
            raise NotFound("No Employee matches the given query.")
        return employee

    def update(self, request, *args, **kwargs):
        """
        Update employee and related user details.
        """
        employee = self.get_object()
        user = request.user

        allowed_roles = {"SuperAdmin", "CompanyOwner", "CompanyAdmin", "CompanyManager"}
        if user.role not in allowed_roles:
            return Response({"error": "You are not authorized to update employee details."},
                            status=status.HTTP_403_FORBIDDEN)

        if user.role != "SuperAdmin" and user.company != employee.company:
            return Response({"error": "You are not authorized to update this employee."},
                            status=status.HTTP_403_FORBIDDEN)

        # --- Step 1: Update the related User object ---
        user_data = request.data.get("user")
        if user_data:
            user_serializer = UserSerializer(employee.user, data=user_data, partial=True)
            if user_serializer.is_valid():
                user_serializer.save()
            else:
                return Response({"user_errors": user_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # --- Step 2: Update Employee fields (from root-level data) ---
        # Cleaned data: remove nested user data before passing to serializer
        employee_data = request.data.copy()
        employee_data.pop("user", None)

        serializer = self.get_serializer(employee, data=employee_data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """
        Partially update an employee's details.
        Only SuperAdmin, CompanyOwner, CompanyAdmin, and CompanyManager can update.
        """
        employee = self.get_object()
        user = request.user

        allowed_roles = {"SuperAdmin", "CompanyOwner", "CompanyAdmin", "CompanyManager"}
        if user.role not in allowed_roles:
            return Response({"error": "You are not authorized to update employee details."},
                            status=status.HTTP_403_FORBIDDEN)

        if user.role != "SuperAdmin" and user.company != employee.company:
            return Response({"error": "You are not authorized to update this employee"},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(employee, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Employee {employee.id} partially updated by {user.email}")
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """
        Mark employee as deleted instead of actually removing them from the database.
        """
        employee = self.get_object()
        user = request.user
        allowed_roles = {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}

        # Only allowed roles can delete
        if user.role not in allowed_roles:
            return Response({"error": "You are not authorized to delete employees."}, status=status.HTTP_403_FORBIDDEN)

        # Ensure non-SuperAdmins can only delete employees in their company
        if user.role != "SuperAdmin" and user.company != employee.company:
            return Response({"error": "You are not authorized to delete this employee."},
                            status=status.HTTP_403_FORBIDDEN)

        # Mark the employee as deleted
        employee.is_deleted = True
        employee.date_deleted = timezone.now()
        employee.save()

        # Log the deletion event
        logger.warning(f"Employee {employee.id} marked as deleted by {user.email}")

        return Response({"message": "Employee marked as deleted"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="change-password")
    def handle_change_password(self, request, company_pk=None, pk=None):
        """
        Handle password change for employees.
        Company owners can change any employee's password.
        Employees can only change their own password and must provide current password.
        """
        try:
            # Get the employee instance
            employee = self.get_object()
            user_to_change = employee.user
            requesting_user = request.user

            # Extract data from request
            current_password = request.data.get('currentPassword', '')
            new_password = request.data.get('newPassword', '')
            confirm_password = request.data.get('confirmPassword', '')

            # Validate required fields
            if not new_password:
                return Response(
                    {'error': 'New password is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not confirm_password:
                return Response(
                    {'error': 'Password confirmation is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if passwords match
            if new_password != confirm_password:
                return Response(
                    {'error': 'New password and confirmation do not match'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check permissions
            is_company_owner = requesting_user.role == 'CompanyOwner'
            is_own_account = requesting_user.id == user_to_change.id

            if not (is_company_owner or is_own_account):
                return Response(
                    {'error': 'You do not have permission to change this password'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # If user is changing their own password, verify current password
            if is_own_account and not is_company_owner:
                if not current_password:
                    return Response(
                        {'error': 'Current password is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Verify current password
                if not user_to_change.check_password(current_password):
                    return Response(
                        {'error': 'Current password is incorrect'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Validate new password strength using Django's built-in validators
            try:
                validate_password(new_password, user_to_change)
            except ValidationError as e:
                return Response(
                    {'error': list(e.messages)},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if new password is the same as current password
            if user_to_change.check_password(new_password):
                return Response(
                    {'error': 'New password must be different from current password'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Set the new password
            user_to_change.set_password(new_password)
            user_to_change.save()

            # Log the password change (optional - for audit purposes)
            # You might want to add logging here
            # import logging
            # logger = logging.getLogger(__name__)
            # logger.info(f"Password changed for user {user_to_change.username} by {requesting_user.username}")

            # Return success response
            return Response(
                {
                    'message': 'Password changed successfully',
                    'changed_by': requesting_user.username,
                    'changed_for': user_to_change.username,
                    'timestamp': timezone.now().isoformat()
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            # Log the error
            # import logging
            # logger = logging.getLogger(__name__)
            # logger.error(f"Error changing password: {str(e)}")

            return Response(
                {'error': 'An error occurred while changing the password'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @action(detail=True, methods=["get", "post"], url_path="leaves")
    def handle_leaves(self, request, company_pk=None, pk=None):
        employee = self.get_object()

        if request.method == "GET":
            serializer = EmployeeLeaveSerializer(employee.leaves.all(), many=True)
            return Response(serializer.data)

        elif request.method == "POST":
            data = request.data.copy()
            data["employee"] = employee.id
            serializer = EmployeeLeaveSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["put"], url_path="leaves/(?P<leave_id>[^/.]+)")
    def update_leave(self, request, company_pk=None, pk=None, leave_id=None):
        employee = self.get_object()
        try:
            leave = employee.leaves.get(pk=leave_id)
        except EmployeeLeave.DoesNotExist:
            return Response({"error": "Leave not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EmployeeLeaveSerializer(leave, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # --- REMUNERATION ---
    @action(detail=True, methods=["get", "post", "put"], url_path="remuneration")
    def handle_remuneration(self, request, company_pk=None, pk=None):
        employee = self.get_object()

        if request.method == "GET":
            serializer = EmployeeRemunerationSerializer(employee.remunerations.all(), many=True)
            return Response(serializer.data)

        elif request.method == "POST":
            data = request.data.copy()
            data["employee"] = employee.id
            serializer = EmployeeRemunerationSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == "PUT":
            serializer = EmployeeRemunerationSerializer(employee.remuneration, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # --- DEDUCTIONS ---
    @action(detail=True, methods=["get", "post"], url_path="deductions")
    def handle_deductions(self, request, company_pk=None, pk=None):
        employee = self.get_object()

        if request.method == "GET":
            serializer = EmployeeDeductionSerializer(employee.deductions.all(), many=True)
            return Response(serializer.data)

        elif request.method == "POST":
            data = request.data.copy()
            data["employee"] = employee.id
            serializer = EmployeeDeductionSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({"message":"Deduction added successfully","data":serializer.data}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # --- COMMISSION SETTING ---
    @action(detail=True, methods=["get", "post", "put"], url_path="commission-settings")
    def handle_commission(self, request, company_pk=None, pk=None):
        employee = self.get_object()

        if request.method == "GET":
            serializer = EmployeeCommissionSettingSerializer(employee.commission_settings.all(), many=True)
            return Response(serializer.data)
        elif request.method == "POST":
            data = request.data.copy()
            data["employee"] = employee.id  # Just pass the employee ID, not the serialized object

            serializer = EmployeeCommissionSettingSerializer(data=data)

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"data": serializer.data, "message": "Commission Setting added successfully"},
                    status=status.HTTP_201_CREATED
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == "PUT":
                serializer = EmployeeCommissionSettingSerializer(employee.commission_settings, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="commissions")
    def handle_commissions(self, request, company_pk=None, pk=None):
        employee = self.get_object()

        if request.method == "GET":
            serializer = EmployeeCommissionSerializer(employee.commissions.all(), many=True)
            return Response(serializer.data)
        # elif request.method == "POST":
        #     data = request.data.copy()
        #     data["employee"] = employee.id
        #     serializer = EmployeeCommissionSerializer(data=data)
        #     if serializer.is_valid():
        #         serializer.save()
        #         return Response(serializer.data, status=status.HTTP_201_CREATED)
        #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        #
        # elif request.method == "PUT":
        #     serializer = EmployeeCommissionSerializer(employee.commissions, data=request.data,
        #                                                      partial=True)
        #     if serializer.is_valid():
        #         serializer.save()
        #         return Response(serializer.data)
        #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="update-commissions")
    def handle_commission_payment(self, request, company_pk=None, pk=None):
        """
        Handle marking employee commissions as paid.
        Supports both individual and bulk commission updates.

        Expected payload:
        {
            "commissions": [
                {
                    "id": 1,
                    "paid": true,
                    "paymentDate": "2025-06-08"
                },
                ...
            ]
        }
        """
        try:
            # Get the employee and validate company association
            employee = get_object_or_404(
                Employee.objects.select_related('company'),
                pk=pk,
                company_id=company_pk
            )
            print("DATA. ",request.data)
            # Extract commissions data from request
            commissions_data = request.data.get('commissions', [])

            if not commissions_data:
                return Response(
                    {"error": "No commissions data provided"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate that commissions_data is a list
            if not isinstance(commissions_data, list):
                return Response(
                    {"error": "Commissions data must be a list"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            updated_commissions = []
            errors = []

            # Use database transaction to ensure atomicity
            with transaction.atomic():
                for commission_data in commissions_data:
                    try:
                        # Validate required fields
                        commission_id = commission_data.get('id')
                        paid_status = commission_data.get('paid')
                        payment_date = timezone.now()

                        if commission_id is None:
                            errors.append({"error": "Commission ID is required", "data": commission_data})
                            continue

                        if paid_status is None:
                            errors.append({"error": "Paid status is required", "commission_id": commission_id})
                            continue

                        # Get the commission and validate it belongs to the employee
                        try:
                            commission = EmployeeCommission.objects.select_for_update().get(
                                id=commission_id,
                                employee=employee
                            )
                        except EmployeeCommission.DoesNotExist:
                            errors.append({
                                "error": f"Commission with ID {commission_id} not found for this employee",
                                "commission_id": commission_id
                            })
                            continue

                        # Validate that we're not trying to mark an already paid commission as unpaid
                        if commission.paid and not paid_status:
                            errors.append({
                                "error": f"Cannot mark already paid commission {commission_id} as unpaid",
                                "commission_id": commission_id
                            })
                            continue

                        # Update commission fields
                        commission.paid = paid_status

                        # Set payment date if marking as paid
                        if paid_status:
                            if payment_date:
                                try:
                                    # Parse the date string (assuming YYYY-MM-DD format)
                                    commission.date_paid = timezone.now()
                                except ValueError:
                                    errors.append({
                                        "error": f"Invalid payment date format for commission {commission_id}. Expected YYYY-MM-DD",
                                        "commission_id": commission_id
                                    })
                                    continue
                            else:
                                # Use current date if no payment date provided
                                commission.date_paid = timezone.now()
                        else:
                            # Clear payment date if marking as unpaid
                            commission.date_paid = None

                        # Save the commission
                        commission.save()
                        updated_commissions.append(commission)

                    except Exception as e:
                        errors.append({
                            "error": f"Unexpected error processing commission {commission_data.get('id', 'unknown')}: {str(e)}",
                            "commission_id": commission_data.get('id')
                        })

            # Prepare response
            response_data = {
                "success": True,
                "updated_count": len(updated_commissions),
                "updated_commissions": EmployeeCommissionSerializer(updated_commissions, many=True).data
            }

            # Include errors if any occurred
            if errors:
                response_data["errors"] = errors
                response_data["error_count"] = len(errors)

                # If all operations failed, return 400
                if len(updated_commissions) == 0:
                    response_data["success"] = False
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

                # If some operations failed, return 207 (Multi-Status)
                return Response(response_data, status=status.HTTP_207_MULTI_STATUS)

            # All operations successful
            return Response(response_data, status=status.HTTP_200_OK)

        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee not found or does not belong to the specified company"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"], url_path="role-change")
    def handle_role_change(self, request, company_pk=None, pk=None):
        employee = self.get_object()
        user_id = request.data.get('userId')
        user = User.objects.get(pk=user_id)
        if not user:
            return Response({"error":"The employee could not be found"},status=400)
        new_role = request.data.get('role')
        if new_role:
            user.role = new_role
            user.save()
            return Response({"message":f"Employee role changed to {new_role}"})
        return  Response({"error":"There was an error updating employee role, try again"},status=400)

    @action(detail=True, methods=["post"], url_path="deactivate-employee")
    def handle_employee_deactivate(self, request, company_pk=None, pk=None):

        employee = self.get_object()
        try:
            employee.is_active = False
            employee.save()
            return Response({"message":f"{employee.user.get_full_name()} has been marked inactive and will be excluded in all company operations"},status=200)
        except Exception as e:
            return Response({"error":f"There was an error deactivating employee: {e}"},status=400)

    @action(detail=True, methods=["post"], url_path="reactivate-employee")
    def handle_employee_reactivate(self, request, company_pk=None, pk=None):

        employee = self.get_object()

        try:
            employee.is_active = True
            employee.save()
            return Response({
                             "message": f"{employee.user.get_full_name()} has been marked active and will be included in all company operations"},
                            status=200)
        except Exception as e:
            return Response({"error": f"There was an error reactivating employee: {e}"}, status=400)

from django.db.models import Q
class EmployeeChoicesAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        choices = []
        deduction_types = [{'value': k, 'label': v} for k, v in EmployeeDeduction.DEDUCTION_TYPES]
        leave_types = [{'value': k, 'label': v} for k, v in EmployeeLeave.LEAVE_TYPES]
        leave_statuses = [{'value': k, 'label': v} for k, v in EmployeeLeave.STATUS_CHOICES]
        remuneration_types = [{'value': k, 'label': v} for k, v in EmployeeRemuneration.REMUNERATION_TYPES]
        roles = [{'value': role.value, 'label': role.label} for role in Role if role.label != 'SuperAdmin']
        choices.append({"deduction_types":deduction_types})
        choices.append({"leave_types":leave_types})
        choices.append({"leave_statuses":leave_statuses})
        choices.append({"remuneration_types":remuneration_types})
        choices.append({"roles":roles})
        return Response(choices)
def str_to_bool(value):
    return str(value).lower() in ['true', '1', 'yes','false']
def get_employee_deductions_for_month(employee, month_str):
    """
    Get deductions where both effective_month and end_month fall within the given YYYY-MM.
    """
    try:
        # Parse YYYY-MM to date object for the 1st day of the month
        month_start = datetime.datetime.strptime(month_str, "%Y-%m").date()
    except ValueError:
        raise ValueError("Month must be in YYYY-MM format")

    # Compute first day of the next month to define the exclusive range
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1, day=1)

    # Query: deductions with both effective_month and end_month in this range
    deductions = EmployeeDeduction.objects.filter(
        employee=employee,
        effective_month__lte=month_end,
    ).filter(
        Q(end_month__isnull=True) | Q(end_month__gte=month_start)
    )

    return deductions
class CompanyPayrollAPI(APIView):
    permission_classes = [IsCompanyManager | IsCompanyOwner]

    def post(self, request):
        try:
            company_id = request.data.get("companyId")
            month_str = request.data.get("month")  # Format: YYYY-MM
            include_unpaid_commissions = str_to_bool(request.data.get("include_unpaid_commissions", True))

            if not company_id or not month_str:
                return Response({'status': 'error', 'message': 'Company ID and month are required'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                month = datetime.datetime.strptime(month_str, "%Y-%m")
            except ValueError:
                return Response({'status': 'error', 'message': 'Invalid month format. Use YYYY-MM'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                return Response({'status': 'error', 'message': 'Company not found'}, status=status.HTTP_404_NOT_FOUND)

            employees = Employee.objects.filter(company=company, is_deleted=False, is_active=True).select_related('user')

            if not employees.exists():
                return Response({'status': 'error', 'message': 'No active employees found for this company'}, status=status.HTTP_404_NOT_FOUND)

            payroll_data = []
            total_other_deductions = total_gross = total_nssf = total_shif = total_ahl = total_paye = total_net = Decimal('0')

            for employee in employees:
                base_salary = employee.salary or Decimal('0')

                # Remunerations
                remunerations = EmployeeRemuneration.objects.filter(
                    employee=employee,
                    effective_date__year=month.year,
                    effective_date__month=month.month
                )

                employee_deductions = get_employee_deductions_for_month(employee,month_str)


                allowances = {}
                bonuses = Decimal('0')

                for rem in remunerations:
                    if rem.remuneration_type == "Bonus":
                        bonuses += rem.amount
                    else:
                        allowances[rem.name or rem.remuneration_type] = float(rem.amount)
                        base_salary += rem.amount

                # Commissions
                if include_unpaid_commissions:
                    commissions = EmployeeCommission.objects.filter(
                        employee=employee,
                        date_calculate__year=month.year,
                        date_calculate__month=month.month,
                        paid=False
                    )
                    commission_total = commissions.aggregate(total=Sum('commission_amount'))['total'] or Decimal('0')
                    bonuses += commission_total

                gross_salary = base_salary + bonuses

                if gross_salary <= 0:
                    continue

                # Deductions
                # Deductions
                nssf = min(gross_salary * Decimal("0.06"), Decimal("1080")).quantize(Decimal("0.01"))
                shif = max(gross_salary * Decimal("0.0275"), Decimal("300")).quantize(Decimal("0.01"))
                ahl = (gross_salary * Decimal("0.015")).quantize(Decimal("0.01"))
                taxable_income = gross_salary - (nssf + shif + ahl)
                paye = calculate_paye(taxable_income).quantize(Decimal("0.01"))

                deductions = {
                    "NSSF": float(nssf),
                    "SHIF": float(shif),
                    "AHL": float(ahl),
                    "PAYE": float(paye)
                }

                # Add voluntary/extra deductions
                additional_deductions_total = Decimal('0')
                for d in employee_deductions:
                    label = d.deduction_type.title()
                    amount = float(d.amount)
                    deductions[label] = deductions.get(label, 0.0) + amount
                    additional_deductions_total += Decimal(str(amount))  # ensure Decimal

                # Compute net salary
                net_salary = gross_salary - (nssf + shif + ahl + paye + additional_deductions_total)
                # Save or update payroll
                EmployeePayroll.objects.update_or_create(
                    employee=employee,
                    payment_month=month.month,
                    payment_year=month.year,
                    defaults={
                        'basic_salary': employee.salary or Decimal('0'),
                        'allowances': allowances or {},
                        'bonuses': bonuses or Decimal('0'),
                        'deductions': deductions or {},
                        'payment_method': "bank_transfer",
                        'account_number': employee.account_number or "",
                        'bank_name': employee.bank_name or "",
                        'is_paid': False
                    }
                )

                # Mark commissions as paid
                commissions.update(paid=True, date_paid=timezone.now())

                employee_name = employee.user.get_full_name() or employee.user.username
                payroll_data.append({
                    'employee_id': employee.id,
                    'name': employee_name,
                    'position': employee.position or 'N/A',
                    'employee_number': f"EMP{employee.id:04d}",
                    'gross': gross_salary,
                    'nssf': nssf,
                    'shif': shif,
                    'ahl': ahl,
                    'taxable_income': taxable_income,
                    'paye': paye,
                    'other': additional_deductions_total,
                    'net': net_salary
                })

                total_gross += gross_salary
                total_nssf += nssf
                total_shif += shif
                total_ahl += ahl
                total_paye += paye
                total_net += net_salary
                total_other_deductions+=additional_deductions_total

            if not payroll_data:
                return Response({'status': 'error', 'message': 'No payroll generated. Possibly already exists or no salaries found.'}, status=status.HTTP_404_NOT_FOUND)

            payroll_data.sort(key=lambda x: x['name'])

            summary = {
                'total_employees': len(payroll_data),
                'total_gross': total_gross,
                'total_nssf': total_nssf,
                'total_shif': total_shif,
                'total_ahl': total_ahl,
                'total_paye': total_paye,
                'total_net': total_net,
                'total_other_deductions': total_other_deductions,
                'total_deductions': total_nssf + total_shif + total_ahl + total_paye,
                'average_salary': total_gross / len(payroll_data),
                'generation_date': timezone.now().strftime('%d %B %Y at %I:%M %p'),
                'month_name': month.strftime("%B %Y"),
                'month_short': month.strftime("%b %Y"),
            }

            context = {
                "company": company,
                "month": summary['month_name'],
                "month_year": month_str,
                "payroll": payroll_data,
                "summary": summary,
                "generated_by": request.user.get_full_name() if hasattr(request.user, 'get_full_name') else request.user.username,
                "current_date": timezone.now().strftime('%d %B %Y'),
                "current_time": timezone.now().strftime('%I:%M %p'),
            }

            html_string = render_to_string("payroll_template.html", context)
            output_dir = os.path.join(settings.MEDIA_ROOT, 'payrolls')
            os.makedirs(output_dir, exist_ok=True)

            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"payroll_{company.id}_{month.strftime('%Y_%m')}_{timestamp}.pdf"
            file_path = os.path.join(output_dir, filename)

            HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(file_path)

            file_url = request.build_absolute_uri(os.path.join(settings.MEDIA_URL, 'payrolls', filename))

            return Response({
                'status': 'success',
                'message': f'Payroll generated successfully for {summary["month_name"]}',
                'pdf_url': file_url,
                'filename': filename,
                'summary': {
                    'total_employees': summary['total_employees'],
                    'total_gross': float(summary['total_gross']),
                    'total_net': float(summary['total_net']),
                    'generation_date': summary['generation_date']
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'status': 'error', 'message': f'An error occurred while generating payroll: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# @method_decorator(csrf_exempt, name='dispatch')
class CompanyRegistrationAPIView(APIView):
    """
    Class-based API view for company registration requests.
    """
    # Explicitly set permissions
    permission_classes = [AllowAny]
    authentication_classes = []  # No authentication required

    def get_permissions(self):
        return [permission() for permission in self.permission_classes]

    def post(self, request, *args, **kwargs):
        """Handle POST request for company registration."""
        # Debug prints
        print(f"Request method: {request.method}")
        print(f"Request user: {request.user}")
        print(f"Permission classes: {self.permission_classes}")

        try:
            serializer = CompanyRegistrationSerializer(data=request.data)

            if serializer.is_valid():
                with transaction.atomic():
                    company = serializer.save()

                    logger.info(f"New company registration: {company.name} ({company.email})")

                    return Response({
                        'success': True,
                        'message': 'Company registration request submitted successfully',
                        'data': {
                            'company_id': company.id,
                            'name': company.name,
                            'email': company.email,
                            'subscription_plan': company.subscription_plan,
                            'subscription_fee': str(company.subscription_fee),
                            'created_at': company.created_at.isoformat()
                        }
                    }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'message': 'Validation failed',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Company registration error: {str(e)}", exc_info=True)

            return Response({
                'success': False,
                'message': 'An internal server error occurred',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def send_confirmation_email(self, company):
        """Send confirmation email to the company (implement as needed)."""
        # TODO: Implement email sending logic
        pass