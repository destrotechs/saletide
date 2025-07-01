import re
from decimal import Decimal

from rest_framework import serializers
from .models import Company, Employee,EmployeeCommission,EmployeeCommissionSetting,EmployeeDeduction,EmployeeLeave,EmployeeRemuneration
from django.contrib.auth import get_user_model
from core.serializers import UserSerializer
User = get_user_model()

class CompanySerializer(serializers.ModelSerializer):
    directors = serializers.SerializerMethodField()
    company_logo = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id", "name", "email", "phone", "address",
            "subscription_plan", "subscription_fee",
            "is_active", "directors", "company_logo", "created_at"
        ]
        read_only_fields = ["created_at"]

    def get_directors(self, obj):
        """
        Return only id, name, and email for each director.
        """
        return [
            {"id": director.id, "name": director.get_full_name() or director.username, "email": director.email}
            for director in obj.directors.all()
        ]

    def get_company_logo(self, obj):
        """
        Return the absolute URL of the company logo.
        """
        request = self.context.get('request')
        if obj.company_logo and request:
            return request.build_absolute_uri(obj.company_logo.url)
        return None

class EmployeeSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), write_only=True, source='user'
    )

    class Meta:
        model = Employee
        fields = ['id', 'position', 'company', 'salary', 'date_employed', 'employee_name', 'user', 'user_id','is_active','account_number','bank_branch','bank_name','phone']

    def get_employee_name(self,obj):
        return obj.user.username

class EmployeeCommissionSettingSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    service_name = serializers.CharField(source='service.name', read_only=True)

    class Meta:
        model = EmployeeCommissionSetting
        fields = [
            'id', 'employee', 'service', 'service_name',
            'commission_percentage', 'created_at'
        ]
        read_only_fields = ['created_at']


# EmployeeCommission Serializer
class EmployeeCommissionSerializer(serializers.ModelSerializer):
    employee = EmployeeSerializer(read_only=True)
    sale_item_id = serializers.IntegerField(source='sale_item.id', read_only=True)
    service_name = serializers.CharField(source='sale_item.service.name', read_only=True)
    amount = serializers.DecimalField(source='sale_item.amount', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = EmployeeCommission
        fields = [
            'id', 'sale_item_id', 'service_name', 'amount',
            'employee', 'commission_amount', 'paid',
            'date_paid', 'date_calculate'
        ]


# EmployeeRemuneration Serializer
class EmployeeRemunerationSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())

    class Meta:
        model = EmployeeRemuneration
        fields = [
            'id', 'name', 'employee', 'amount',
            'currency', 'created_at', 'updated_at','remuneration_type','effective_date'
        ]


# EmployeeLeave Serializer
class EmployeeLeaveSerializer(serializers.ModelSerializer):
    employee = EmployeeSerializer(read_only=True)
    reviewed_by = serializers.StringRelatedField()

    class Meta:
        model = EmployeeLeave
        fields = [
            'id', 'employee', 'leave_type', 'start_date', 'end_date',
            'reason', 'status', 'created_at', 'reviewed_at', 'reviewed_by'
        ]


# EmployeeDeduction Serializer
class EmployeeDeductionSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())

    class Meta:
        model = EmployeeDeduction
        fields = [
            'id', 'employee', 'deduction_type', 'amount',
            'reason', 'effective_month', 'created_at','end_month'
        ]


class CompanyRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for company registration requests."""

    subscription_plan = serializers.ChoiceField(
        choices=[('monthly', 'Monthly'), ('annual', 'Annual')],
        default='monthly'
    )

    class Meta:
        model = Company
        fields = [
            'name', 'email', 'phone', 'address',
            'subscription_plan', 'subscription_fee',
            'company_logo'
        ]
        extra_kwargs = {
            'subscription_fee': {'read_only': True},
        }

    def validate_name(self, value):
        """Validate company name."""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Company name must be at least 2 characters long")

        if len(value.strip()) > 255:
            raise serializers.ValidationError("Company name cannot exceed 255 characters")

        return value.strip()

    def validate_email(self, value):
        """Validate email format and uniqueness."""
        email = value.lower().strip()

        # Check if email already exists
        if Company.objects.filter(email=email).exists():
            raise serializers.ValidationError("A company with this email already exists")

        return email

    def validate_phone(self, value):
        """Validate phone number format and uniqueness."""
        # Clean phone number
        clean_phone = re.sub(r'[\s\-\(\)]', '', value)

        # Validate format
        phone_pattern = r'^[\+]?[1-9][\d]{7,15}$'
        if not re.match(phone_pattern, clean_phone):
            raise serializers.ValidationError("Please enter a valid phone number")

        # Check uniqueness
        if Company.objects.filter(phone=clean_phone).exists():
            raise serializers.ValidationError("A company with this phone number already exists")

        return clean_phone

    def validate_address(self, value):
        """Validate address."""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Please provide a more detailed address (minimum 10 characters)")

        if len(value.strip()) > 1000:
            raise serializers.ValidationError("Address is too long (maximum 1000 characters)")

        return value.strip()

    # def validate_company_logo(self, value):
    #     """Validate company logo file."""
    #     if value:
    #         # Check file size (5MB limit)
    #         if value.size > 5 * 1024 * 1024:
    #             raise serializers.ValidationError("Logo file size cannot exceed 5MB")
    #
    #         # Check file type
    #         allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
    #         if value.content_type not in allowed_types:
    #             raise serializers.ValidationError("Logo must be a valid image file (JPEG, PNG, GIF)")
    #
    #     return value

    def create(self, validated_data):
        """Create company instance with calculated subscription fee."""
        # Set subscription fee based on plan
        subscription_plan = validated_data['subscription_plan']
        if subscription_plan == 'monthly':
            validated_data['subscription_fee'] = Decimal('3000.00')
        else:  # annual
            validated_data['subscription_fee'] = Decimal('30000.00')

        # Set default values
        validated_data['is_active'] = True
        validated_data['is_deleted'] = False

        return super().create(validated_data)