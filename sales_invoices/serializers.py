from rest_framework import serializers
from datetime import date
from .models import Sale, Invoice,SaleItemRequirement,SaleItem,SaleItemEmployee,Payment,PaymentInvoice,PaymentSale
from customers.models import Customer
from inventory.models import InventoryItem
from services.models import Service
from companies.serializers import EmployeeSerializer

from rest_framework import serializers
from companies.models import Employee  # adjust this import based on your structure
from companies.serializers import EmployeeSerializer


class DashboardInsightsSerializer(serializers.Serializer):
    total_sales = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    monthly_sales = serializers.IntegerField()
    monthly_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_services = serializers.IntegerField()
    total_products = serializers.IntegerField()
    total_service_sale_amount = serializers.IntegerField()
    total_product_sale_amount = serializers.IntegerField()


class SaleItemEmployeeSerializer(serializers.ModelSerializer):
    employee = EmployeeSerializer(read_only=True)  # <-- use the nested serializer

    class Meta:
        model = SaleItemEmployee
        fields = ['id', 'employee']



class SaleItemSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    assigned_employees = SaleItemEmployeeSerializer(many=True, read_only=True)

    # This is for writing employees — optional, if you're assigning via API
    employees = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), many=True, write_only=True, required=False
    )

    class Meta:
        model = SaleItem
        fields = [
            'id', 'sale', 'type', 'service', 'service_name',
            'product', 'product_name', 'quantity', 'amount',
            'assigned_employees', 'employees','tax_rate','tax_amount','subtotal','total','discount_rate','discount_amount'
        ]


class SaleSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate_number', read_only=True)
    sale_items = SaleItemSerializer(many=True, read_only=True, source='items')
    serviced_vehicle = serializers.SerializerMethodField()
    sale_amount = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            'id', 'company', 'customer', 'customer_name',
            'vehicle', 'vehicle_plate', 'date',
            'is_deleted', 'is_invoiced', 'deleted_at',
            'sale_items','serviced_vehicle','sale_amount','status'
        ]
    def get_serviced_vehicle(self,obj):
        if obj.vehicle:
            return f"{obj.vehicle.model}-{obj.vehicle.plate_number}"
        else:
            return ''
    def get_sale_amount(self,obj):
        amount = 0
        taxes = 0
        discount = 0
        for item in obj.items.all():
            amount+=item.total
            # taxes+=item.tax_amount
            # discount+=item.discount_amount

        return amount


class InvoiceSerializer(serializers.ModelSerializer):
    sales = serializers.PrimaryKeyRelatedField(queryset=Sale.objects.all(), many=True, write_only=True)
    sale_details = SaleSerializer(source='sales', many=True, read_only=True)  # <-- Add this line
    invoice_amount = serializers.SerializerMethodField()
    class Meta:
        model = Invoice
        fields = ['id','company', 'sales', 'sale_details','due_date', 'status', 'invoice_number', 'date_created','customer','invoice_amount']
        read_only_fields = ['invoice_number', 'date_created']

    def validate_due_date(self, value):
        # Ensure the due date is in the future
        if value <= date.today():
            raise serializers.ValidationError("Due date must be in the future.")
        return value

    def validate_status(self, value):
        if value not in ['Pending', 'Paid']:
            raise serializers.ValidationError("Status must be either 'Pending' or 'Paid'.")
        return value

    def get_invoice_amount(self, obj):
        amount = 0
        for sale in obj.sales.all():  # Access related sales directly
            for item in sale.items.all():  # Assuming each sale has related items
                amount += item.amount  # Access the amount of each item
        return amount
class PaymentInvoiceSerializer(serializers.ModelSerializer):
    invoice = InvoiceSerializer()

    class Meta:
        model = PaymentInvoice
        fields = ['invoice']


class PaymentSaleSerializer(serializers.ModelSerializer):
    sale = SaleSerializer()

    class Meta:
        model = PaymentSale
        fields = ['sale']


class PaymentSerializer(serializers.ModelSerializer):
    invoices = serializers.SerializerMethodField()
    sales = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id', 'amount_paid', 'date_paid', 'payment_method', 'transaction_id',
            'checkoutrequest_id', 'is_deleted', 'deleted_at', 'remarks',
            'invoices', 'sales'
        ]

    def get_invoices(self, obj):
        invoices = PaymentInvoice.objects.filter(payment=obj)
        return PaymentInvoiceSerializer(invoices, many=True).data

    def get_sales(self, obj):
        sales = PaymentSale.objects.filter(payment=obj)
        return PaymentSaleSerializer(sales, many=True).data