from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import (
    Customer, CustomerVehicle, LoyaltyPoint, CustomerServiceRecord,
    CustomerRedemption, CustomerAppointment
)
from .serializers import (
    CustomerSerializer, CustomerVehicleSerializer, LoyaltyPointSerializer,
    CustomerServiceRecordSerializer, CustomerRedemptionSerializer, CustomerAppointmentSerializer,AppointmentService
)

from core.permissions import IsSuperAdmin, IsCompanyOwnerOrAdmin, IsCompanyManager,IsCompanyOwner,IsCompanyActive
from .utilities import send_email,create_html_template,send_welcome_email
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView
from services.models import Service
from django.db import transaction
class CustomerViewSet(viewsets.ModelViewSet):
    """
    Manage Customer CRUD with role-based access:
    - SuperAdmins: full access
    - CompanyOwner/Admin/Manager: only within their own company
    - Others: denied
    """
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsCompanyOwnerOrAdmin | IsCompanyManager,IsCompanyActive]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SuperAdmin":
            return Customer.objects.all()
        return Customer.objects.filter(company=user.company, is_deleted=False)

    def perform_create(self, serializer):
        user = self.request.user
        company = serializer.validated_data.get("company")

        if user.role == "SuperAdmin":
            serializer.save()
        elif user.role in ["CompanyOwner", "CompanyAdmin", "CompanyManager"]:
            if company != user.company:
                raise PermissionDenied("You can only create customers within your own company.")
            serializer.save()

        else:
            raise PermissionDenied("You do not have permission to create a customer.")

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.data = {
            "message": "Customer created successfully.",
            "data": response.data
        }
        return response

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if user.role == "SuperAdmin":
            serializer.save()
        elif instance.company == user.company and user.role in ["CompanyOwner", "CompanyAdmin", "CompanyManager"]:
            serializer.save()
        else:
            raise PermissionDenied("You can only update customers in your own company.")

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        response.data = {
            "message": "Customer updated successfully.",
            "data": response.data
        }
        return response
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user

        if user.role == "SuperAdmin" or (
                instance.company == user.company and user.role in  ["CompanyOwner", "CompanyAdmin", "CompanyManager"]):
            instance.is_deleted = True
            instance.deleted_at = timezone.now()
            instance.save()
            return Response({"message": "Customer deleted  successfully."}, status=status.HTTP_200_OK)
        else:
            raise PermissionDenied("You do not have permission to delete this customer.")


class CustomerVehicleViewSet(viewsets.ModelViewSet):
    """
    View for managing customer vehicles.
    - SuperAdmins, Company Owners, and Admins can manage vehicles.
    - Managers can only view.
    """
    queryset = CustomerVehicle.objects.all()
    serializer_class = CustomerVehicleSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsCompanyOwnerOrAdmin | IsCompanyManager,IsCompanyActive]

    def get_queryset(self):
        user = self.request.user
        customer_id = self.request.query_params.get("customer")

        qs = CustomerVehicle.objects.filter(is_deleted=False)

        if user.role != "SuperAdmin":
            qs = qs.filter(customer__company=user.company)

        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        return qs
    def perform_create(self, serializer):
        user = self.request.user
        customer = serializer.validated_data.get("customer")

        # Check if the customer is deleted
        if customer.is_deleted:
            raise ValidationError("You cannot add a vehicle to a deleted customer.")

        if user.role == "SuperAdmin":
            serializer.save()
        elif customer.company == user.company and user.role in ["CompanyOwner", "CompanyAdmin"]:
            serializer.save()
        else:
            raise PermissionDenied("You cannot add a vehicle to a customer in a different company.")

    def create(self, request, *args, **kwargs):
        try:
            response = super().create(request, *args, **kwargs)
            response.data = {
                "message": "Customer vehicle created successfully.",
                "data": response.data
            }
            return response
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Failed to create vehicle: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        user = self.request.user
        vehicle = self.get_object()

        # Check if the vehicle is deleted
        if vehicle.is_deleted:
            raise ValidationError("You cannot update a deleted vehicle.")

        # Get the new customer if provided, otherwise default to the current customer
        new_customer = serializer.validated_data.get("customer", vehicle.customer)

        # Ensure the vehicle's registration number (plate_number) is not being duplicated
        new_plate_number = serializer.validated_data.get("plate_number", vehicle.plate_number)

        if CustomerVehicle.objects.filter(plate_number=new_plate_number).exclude(id=vehicle.id).exists():
            raise ValidationError(f"A vehicle with registration number {new_plate_number} already exists.")

        if user.role == "SuperAdmin":
            serializer.save()
        elif vehicle.customer.company == user.company and new_customer.company == user.company and user.role in [
            "CompanyOwner", "CompanyAdmin"]:
            serializer.save()
        else:
            raise PermissionDenied("You cannot update vehicles outside your company.")
    def update(self, request, *args, **kwargs):

        try:
            request.data.pop('plate_number', None)
            response = super().update(request, *args, **kwargs)
            # response.data = {
            #     "message": "Customer vehicle updated successfully.",
            #     "data": response.data
            # }
            return response
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Failed to update vehicle: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        try:
            response = super().partial_update(request, *args, **kwargs)
            return Response({
                "message": "Customer vehicle partially updated successfully.",
                "data": response.data
            }, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except CustomerVehicle.DoesNotExist:
            return Response({"error": "Customer vehicle not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Failed to update vehicle: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            user = request.user

            if user.role == "SuperAdmin" or (
                instance.customer.company == user.company and user.role in ["CompanyOwner", "CompanyAdmin"]
            ):
                instance.is_deleted = True
                instance.deleted_at = timezone.now()
                instance.save()
                return Response({"message": "Customer vehicle deleted successfully."}, status=status.HTTP_200_OK)
            else:
                raise PermissionDenied("You do not have permission to delete this vehicle.")
        except NotFound:
            return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Failed to delete vehicle: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

class LoyaltyPointViewSet(viewsets.ModelViewSet):
    """
    View for managing loyalty points.
    - SuperAdmins and Company Owners/Admins have full control.
    - Managers can view loyalty points but not modify them.
    """
    queryset = LoyaltyPoint.objects.all()
    serializer_class = LoyaltyPointSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsCompanyOwnerOrAdmin | IsCompanyManager|IsCompanyActive]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SuperAdmin":
            return LoyaltyPoint.objects.all()

        customer_id = self.request.query_params.get("customer")
        if customer_id:
            return LoyaltyPoint.objects.filter(customer__id=customer_id, customer__company=user.company)
        return LoyaltyPoint.objects.filter(customer__company=user.company)

    def list(self, request, *args, **kwargs):
        customer_id = request.query_params.get("customer")
        if not customer_id:
            return super().list(request, *args, **kwargs)

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        # Loyalty points earned
        points = LoyaltyPoint.objects.filter(customer=customer)
        points_data = LoyaltyPointSerializer(points, many=True).data

        # Redeemed points
        redemptions = CustomerRedemption.objects.filter(customer=customer)
        redemption_data = CustomerRedemptionSerializer(redemptions, many=True).data

        return Response({
            "loyalty_points": points_data,
            "redeemed_points": redemption_data
        })
    def perform_create(self, serializer):
        user = self.request.user
        customer = serializer.validated_data.get("customer")

        if customer.is_deleted:
            raise PermissionDenied("Cannot assign loyalty points to a deleted customer.")

        if user.role == "SuperAdmin":
            serializer.save()
        elif customer.company == user.company and user.role in ["CompanyOwner", "CompanyAdmin"]:
            serializer.save()
        else:
            raise PermissionDenied("You cannot add loyalty points to a customer in a different company.")

    def create(self, request, *args, **kwargs):
        try:
            response = super().create(request, *args, **kwargs)
            return Response({
                "message": "Loyalty points added successfully.",
                "data": response.data
            }, status=status.HTTP_201_CREATED)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Failed to add loyalty points: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        try:
            response = super().update(request, *args, **kwargs)
            return Response({
                "message": "Loyalty points updated successfully.",
                "data": response.data
            }, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except LoyaltyPoint.DoesNotExist:
            return Response({"error": "Loyalty point record not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Failed to update loyalty points: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        try:
            response = super().partial_update(request, *args, **kwargs)
            return Response({
                "message": "Loyalty points partially updated successfully.",
                "data": response.data
            }, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except LoyaltyPoint.DoesNotExist:
            return Response({"error": "Loyalty point record not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Failed to update loyalty points: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()

            user = request.user
            if user.role != "SuperAdmin" and instance.customer.company != user.company:
                raise PermissionDenied("You cannot delete loyalty points from a different company.")

            self.perform_destroy(instance)
            return Response({"message": "Loyalty points deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except LoyaltyPoint.DoesNotExist:
            return Response({"error": "Loyalty point record not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Failed to delete loyalty points: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
class CustomerServiceRecordViewSet(viewsets.ModelViewSet):
    """
    View for managing customer service records.
    - SuperAdmins and Company Owners/Admins have full control.
    - Managers can only view service records.
    """
    queryset = CustomerServiceRecord.objects.all()
    serializer_class = CustomerServiceRecordSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsCompanyOwnerOrAdmin | IsCompanyManager | IsCompanyActive]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SuperAdmin":
            return CustomerServiceRecord.objects.all()

        customer_id = self.request.query_params.get("customer")
        queryset = CustomerServiceRecord.objects.filter(customer__company=user.company)
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        customer = serializer.validated_data.get("customer")

        if customer.is_deleted:
            raise PermissionDenied("Cannot create a service record for a deleted customer.")

        if user.role == "SuperAdmin":
            serializer.save()
        elif customer.company == user.company and user.role in ["CompanyOwner", "CompanyAdmin"]:
            serializer.save()
        else:
            raise PermissionDenied("You cannot create a service record for a customer in a different company.")

    def create(self, request, *args, **kwargs):
        print("Request data",request.data)
        try:
            response = super().create(request, *args, **kwargs)
            return Response({
                "message": "Customer service record created successfully.",
                "data": response.data
            }, status=status.HTTP_201_CREATED)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Failed to create service record: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.role != "SuperAdmin" and instance.customer.company != request.user.company:
                raise PermissionDenied("You cannot update a service record in a different company.")
            response = super().update(request, *args, **kwargs)
            return Response({
                "message": "Customer service record updated successfully.",
                "data": response.data
            }, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Failed to update service record: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.role != "SuperAdmin" and instance.customer.company != request.user.company:
                raise PermissionDenied("You cannot update a service record in a different company.")
            response = super().partial_update(request, *args, **kwargs)
            return Response({
                "message": "Customer service record partially updated successfully.",
                "data": response.data
            }, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Failed to update service record: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.role != "SuperAdmin" and instance.customer.company != request.user.company:
                raise PermissionDenied("You cannot delete a service record in a different company.")
            self.perform_destroy(instance)
            return Response({"message": "Customer service record deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Failed to delete service record: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

class CustomerRedemptionViewSet(viewsets.ModelViewSet):
    """
    View for managing customer redemptions.
    - SuperAdmins and Company Owners/Admins can manage redemptions.
    - Managers can only view redemptions.
    """
    queryset = CustomerRedemption.objects.all()
    serializer_class = CustomerRedemptionSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsCompanyOwnerOrAdmin | IsCompanyManager | IsCompanyActive]

    def get_queryset(self):
        if self.request.user.role == "SuperAdmin":
            return CustomerRedemption.objects.all()
        return CustomerRedemption.objects.filter(customer__company=self.request.user.company)


from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied


class CustomerAppointmentViewSet(viewsets.ModelViewSet):
    """
    View for managing customer appointments.
    - SuperAdmins and Company Owners/Admins can manage appointments.
    - Managers can only view appointments.
    """
    queryset = CustomerAppointment.objects.all()
    serializer_class = CustomerAppointmentSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsCompanyOwnerOrAdmin | IsCompanyManager | IsCompanyActive]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SuperAdmin":
            return CustomerAppointment.objects.all()

        customer_id = self.request.query_params.get("customer")
        queryset = CustomerAppointment.objects.filter(customer__company=user.company).order_by('-appointment_date')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id).order_by('-appointment_date')
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            # Extract and clean the data
            data = request.data.copy()
            services_data = data.pop('services', [])

            # Remove fields that shouldn't be in the appointment creation
            data.pop('service', None)  # Remove concatenated service string
            data.pop('customer_name', None)  # Remove customer name
            data.pop('price', None)  # Remove the submitted price

            # Create serializer with cleaned data
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)

            # Permission checks
            customer = serializer.validated_data.get("customer")
            if customer.is_deleted:
                raise PermissionDenied("Cannot create an appointment for a deleted customer.")

            user = request.user
            if user.role != "SuperAdmin":
                if customer.company != user.company or user.role not in ["CompanyOwner", "CompanyAdmin"]:
                    raise PermissionDenied("You cannot create an appointment for a customer in a different company.")

            # Create the appointment (without calling serializer.save() to avoid the service issue)
            appointment = CustomerAppointment.objects.create(**serializer.validated_data)

            # Process services
            total_price = 0
            for service_data in services_data:
                service_id = service_data.get('id')
                if service_id:
                    try:
                        service = Service.objects.get(id=service_id)
                        AppointmentService.objects.create(
                            appointment=appointment,
                            service=service,
                            price=service.price,
                        )
                        total_price += float(service.price)
                    except Service.DoesNotExist:
                        raise ValueError(f"Service with id {service_id} does not exist")

            # Update total price
            appointment.total_price = total_price
            appointment.save(update_fields=['total_price'])

            return Response({
                "message": "Customer appointment created successfully.",
            }, status=status.HTTP_200_OK)

        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Failed to create appointment: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.role != "SuperAdmin" and instance.customer.company != request.user.company:
                raise PermissionDenied("You cannot update an appointment in a different company.")

            # Handle services update if provided
            data = request.data.copy()
            services_data = data.pop('services', None)

            # Clean the data
            data.pop('service', None)
            data.pop('customer_name', None)
            data.pop('price', None)

            serializer = self.get_serializer(instance, data=data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)

            # Update the appointment fields
            for attr, value in serializer.validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Update services if provided
            if services_data is not None:
                # Clear existing services
                AppointmentService.objects.filter(appointment=instance).delete()

                # Add new services
                total_price = 0
                for service_data in services_data:
                    service_id = service_data.get('id')
                    if service_id:
                        try:
                            service = Service.objects.get(id=service_id)
                            AppointmentService.objects.create(
                                appointment=instance,
                                service=service,
                            )
                            total_price += float(service.price)
                        except Service.DoesNotExist:
                            raise ValueError(f"Service with id {service_id} does not exist")

                # Update total price
                instance.total_price = total_price
                instance.save(update_fields=['total_price'])

            response_serializer = self.get_serializer(instance)
            return Response({
                "message": "Customer appointment updated successfully.",
                "data": response_serializer.data
            }, status=status.HTTP_200_OK)

        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Failed to update appointment: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if request.user.role != "SuperAdmin" and instance.customer.company != request.user.company:
                raise PermissionDenied("You cannot delete an appointment in a different company.")
            self.perform_destroy(instance)
            return Response({"message": "Customer appointment deleted successfully."},
                            status=200)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Failed to delete appointment: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


class CustomerNotificationAPI(APIView):
    permission_classes = [IsCompanyManager|IsCompanyOwner|IsCompanyActive]
    def post(self,request):
        customer_id = request.data.get('customer')
        message = request.data.get("message")
        customer = Customer.objects.get(pk=customer_id)
        if not customer:
            return Response({"error":"The Customer is not registered"},status=400)

        if customer and customer.email:
            html_template = create_html_template("Service Completed",message)

            email_sent = send_email(customer.email,"Service Completed",message,html_template)
            if email_sent:
                return Response({"message":"The Email Notification has been sent successfully"},status=200)
            return Response({"error":"There was a problem sending email notification, Please try again"},status=400)

        else:
            return Response({"error":"The customer has no registered email"},status=400)