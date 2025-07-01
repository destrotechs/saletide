from rest_framework import serializers

from services.models import Service
from services.serializers import ServiceSerializer
from .models import (
    Customer,
    CustomerVehicle,
    LoyaltyPoint,
    CustomerServiceRecord,
    CustomerRedemption,
    CustomerAppointment,
CustomerAddress,
AppointmentService
)

class CustomerAddressSerializer(serializers.ModelSerializer):
    formatted_address = serializers.ReadOnlyField()

    class Meta:
        model = CustomerAddress
        fields = [
            'id',
            'city',
            'street',
            'state',
            'zip_code',
            'formatted_address',
            'created_at',
        ]
        read_only_fields = ['created_at', 'formatted_address']
class CustomerSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    addresses = serializers.SerializerMethodField()
    address = CustomerAddressSerializer(write_only=True, required=False)

    class Meta:
        model = Customer
        fields = ['id', 'company', 'company_name', 'full_name', 'email',
                  'phone', 'created_at', 'contact_person', 'contact_phone',
                  'business_name', 'addresses','currency','billing_name','address']
        read_only_fields = ['created_at']

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None

    def get_addresses(self, obj):
        addresses = obj.addresses.filter(is_deleted=False)
        return CustomerAddressSerializer(addresses, many=True).data

    def create(self, validated_data):
        print("validated_data =", validated_data)
        address_data = validated_data.pop("address", None)
        customer = Customer.objects.create(**validated_data)

        if address_data:
            CustomerAddress.objects.create(customer=customer, **address_data)

        return customer

    def update(self, instance, validated_data):
        # Update customer fields
        company_data = validated_data.pop('company', None)
        address_data = validated_data.pop('address', None)

        # Update the customer instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # If the address data exists, check if an address already exists
        if address_data:
            # Check if an address already exists for the customer
            existing_address = instance.addresses.filter(is_deleted=False).first()

            if existing_address:
                # If an existing address is found, update it
                for attr, value in address_data.items():
                    setattr(existing_address, attr, value)
                existing_address.save()
            else:
                # If no existing address is found, create a new one
                CustomerAddress.objects.create(customer=instance, **address_data)

        instance.save()
        return instance


class CustomerVehicleSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomerVehicle
        fields = ['id', 'customer', 'customer_name', 'model', 'plate_number','make','year','color']

    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else None

    def validate_plate_number(self, value):
        """Validate that plate number is unique"""
        if CustomerVehicle.objects.filter(plate_number=value).exists():
            raise serializers.ValidationError("A vehicle with this plate number already exists")
        return value


class LoyaltyPointSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = LoyaltyPoint
        fields = ['id', 'customer', 'customer_name', 'points', 'last_updated']
        read_only_fields = ['last_updated']

    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else None


class CustomerServiceRecordSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    vehicle_details = serializers.SerializerMethodField()
    service = ServiceSerializer()
    class Meta:
        model = CustomerServiceRecord
        fields = ['id', 'customer', 'customer_name', 'vehicle',
                  'vehicle_details', 'service', 'date_completed']

    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else None

    def get_vehicle_details(self, obj):
        if not obj.vehicle:
            return None
        return {
            'model': obj.vehicle.model,
            'plate_number': obj.vehicle.plate_number
        }


class CustomerRedemptionSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomerRedemption
        fields = ['id', 'customer', 'customer_name', 'points_used', 'date_redeemed']
        read_only_fields = ['date_redeemed']

    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else None

    def validate_points_used(self, value):
        """Validate that points being used is a positive integer"""
        if value <= 0:
            raise serializers.ValidationError("Points used must be a positive number")
        return value


class CustomerAppointmentSerializer(serializers.ModelSerializer):
    services_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
        # Remove the source='services' line - this is causing the error
    )
    services = serializers.SerializerMethodField(read_only=True)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    service = serializers.SerializerMethodField(read_only=True)  # For backward compatibility

    class Meta:
        model = CustomerAppointment
        fields = [
            'id', 'customer', 'customer_name', 'services_data', 'services', 'service',
            'appointment_date', 'start_time', 'end_time', 'status',
            'notes', 'total_price', 'created_at', 'updated_at'
        ]
        read_only_fields = ['total_price', 'created_at', 'updated_at']

    def get_services(self, obj):
        """Get all services for this appointment"""
        if not obj.pk:
            return []

        try:
            appointment_services = AppointmentService.objects.filter(
                appointment=obj
            ).select_related('service')

            services_list = []
            for as_obj in appointment_services:
                try:
                    # Safely get each field and convert non-serializable objects
                    service_data = {
                        'id': as_obj.service.id,
                        'name': as_obj.service.name,
                        'description': str(getattr(as_obj.service, 'description', '')),
                        'requires_products': bool(getattr(as_obj.service, 'requires_products', False)),
                    }

                    # Handle company field safely
                    if hasattr(as_obj.service, 'company') and as_obj.service.company:
                        service_data['company'] = as_obj.service.company.id
                    else:
                        service_data['company'] = None

                    # Handle price and numeric fields
                    try:
                        service_data['price'] = str(as_obj.get_effective_price())
                    except:
                        service_data['price'] = "0.00"

                    try:
                        service_data['duration_minutes'] = int(as_obj.get_effective_duration())
                    except:
                        service_data['duration_minutes'] = 0

                    try:
                        service_data['tax_rate'] = str(getattr(as_obj.service, 'tax_rate', '0.00'))
                    except:
                        service_data['tax_rate'] = "0.00"

                    try:
                        service_data['discount_rate'] = str(getattr(as_obj.service, 'discount_rate', '0.00'))
                    except:
                        service_data['discount_rate'] = "0.00"

                    # Handle list fields safely
                    try:
                        item_types = getattr(as_obj.service, 'item_types', [])
                        if hasattr(item_types, 'all'):  # If it's a RelatedManager
                            service_data['item_types'] = [str(item) for item in item_types.all()]
                        elif isinstance(item_types, list):
                            service_data['item_types'] = [str(item) for item in item_types]
                        else:
                            service_data['item_types'] = []
                    except:
                        service_data['item_types'] = []

                    try:
                        products_display = getattr(as_obj.service, 'service_products_display', [])
                        if hasattr(products_display, 'all'):  # If it's a RelatedManager
                            service_data['service_products_display'] = [str(item) for item in products_display.all()]
                        elif isinstance(products_display, list):
                            service_data['service_products_display'] = [str(item) for item in products_display]
                        else:
                            service_data['service_products_display'] = []
                    except:
                        service_data['service_products_display'] = []

                    services_list.append(service_data)

                except Exception as e:
                    print(f"Error processing individual service {as_obj.service.id}: {e}")
                    continue

            return services_list

        except Exception as e:
            print(f"Error getting services: {e}")
            return []

    def get_service(self, obj):
        """For backward compatibility - returns concatenated service names"""
        if not obj.pk:
            return ""

        try:
            appointment_services = AppointmentService.objects.filter(
                appointment=obj
            ).select_related('service')
            service_names = [as_obj.service.name for as_obj in appointment_services]
            return ", ".join(service_names)
        except Exception as e:
            print(f"Error getting service names: {e}")
            return ""

    def create(self, validated_data):
        # Handle services_data separately in the ViewSet
        services_data = validated_data.pop('services_data', [])
        appointment = CustomerAppointment.objects.create(**validated_data)

        # If you want to handle services creation here, add it:
        # self._create_appointment_services(appointment, services_data)

        return appointment

    def update(self, instance, validated_data):
        # Remove services_data if present, it's handled in the ViewSet
        services_data = validated_data.pop('services_data', None)

        # If you want to handle services update here, add it:
        # if services_data is not None:
        #     self._update_appointment_services(instance, services_data)

        return super().update(instance, validated_data)

    def _create_appointment_services(self, appointment, services_data):
        """Helper method to create appointment services"""
        for service_data in services_data:
            AppointmentService.objects.create(
                appointment=appointment,
                service_id=service_data.get('service_id'),
                # Add other fields as needed
            )

    def _update_appointment_services(self, appointment, services_data):
        """Helper method to update appointment services"""
        # Clear existing services
        AppointmentService.objects.filter(appointment=appointment).delete()

        # Create new services
        self._create_appointment_services(appointment, services_data)