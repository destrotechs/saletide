from datetime import date

from django.utils import timezone
from django.utils.timezone import now
from django.db import models
from django.core.exceptions import ValidationError
from companies.models import Company
from customers.models import Customer,CustomerVehicle
from .managers import SaleManager

class Sale(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, blank=True, null=True)
    vehicle = models.ForeignKey(CustomerVehicle, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    is_invoiced = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Paid', 'Paid')], default='Pending')
    objects = SaleManager()
    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Sale #{self.id} - {self.customer.full_name if self.customer else 'No Customer'}"

class SaleItem(models.Model):
    SALE_TYPE_CHOICES = (
        ('service', 'Service'),
        ('product', 'Product'),
    )

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    type = models.CharField(max_length=10, choices=SALE_TYPE_CHOICES)
    service = models.ForeignKey("services.Service", on_delete=models.CASCADE, blank=True, null=True)
    product = models.ForeignKey("inventory.InventoryItem", on_delete=models.CASCADE, blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2,default=0.0)
    tax_rate = models.DecimalField(max_digits=10, decimal_places=2,default=0.0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2,default=0.0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2,default=0.0)
    total = models.DecimalField(max_digits=10, decimal_places=2,default=0.0)
    discount_rate = models.DecimalField(max_digits=10, decimal_places=2,default=0.0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2,default=0.0)
    status = models.CharField(max_length=20,blank=True,null=True)

    def __str__(self):
        if self.type == 'service':
            return f"Service: {self.service.name}"
        return f"Product: {self.product.name}"

    def clean(self):
        if self.type == 'service' and not self.service:
            raise ValidationError("Service must be set for service type.")
        if self.type == 'product' and not self.product:
            raise ValidationError("Product must be set for product type.")
        if self.amount <= 0 or self.quantity <= 0:
            raise ValidationError("Amount and quantity must be positive.")
class SaleItemEmployee(models.Model):
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, related_name="assigned_employees")
    employee = models.ForeignKey('companies.Employee', on_delete=models.CASCADE)

    class Meta:
        unique_together = ("sale_item", "employee")


class SaleItemRequirement(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="sale_inventory_requirements")
    inventory_item = models.ForeignKey("inventory.InventoryItem", on_delete=models.CASCADE, related_name="sale_usages")
    quantity_required = models.PositiveIntegerField(help_text="Amount of inventory item needed per service")

    class Meta:
        unique_together = ('sale', 'inventory_item')

class Invoice(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    sales = models.ManyToManyField(Sale,related_name="invoices",blank=True)  # Change to ManyToManyField for multiple sales
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=100,unique=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    date_created = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Paid', 'Paid')],default='Pending')

    def __str__(self):
        return f"Invoice {self.id} - {self.status}"

    def clean(self):
        """Ensure the due date is in the future and that the status aligns with the sale's status."""
        if not self.pk:
            # Skip validation if the invoice hasn't been saved yet
            return
        # Ensure that the sales in the invoice are not deleted
        for sale in self.sales.all():
            if sale.is_deleted:
                raise ValidationError(f"Cannot create an invoice for a deleted sale with ID {sale.id}.")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.clean()

        # First save to get ID
        super().save(*args, **kwargs)

        # If it's new and invoice_number is empty, generate it and save again
        if is_new and not self.invoice_number:
            today_str = now().strftime('%Y%m%d')
            self.invoice_number = f"INV-{today_str}-{self.id}"
            super().save(update_fields=['invoice_number'])

class SoftDeleteManager(models.Manager):
    """Custom manager to handle soft deletions."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def deleted(self):
        return super().get_queryset().filter(is_deleted=True)

class Payment(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date_paid = models.DateField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    checkoutrequest_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    def delete(self, *args, **kwargs):
        """Soft delete the payment."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def __str__(self):
        return f"Payment of {self.amount_paid} ({self.payment_method})"


class PaymentInvoice(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('payment', 'invoice')

    def __str__(self):
        return f"Payment {self.payment.id} for Invoice #{self.invoice.invoice_number}"


class PaymentSale(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('payment', 'sale')

    def __str__(self):
        return f"Payment {self.payment.id} for Sale #{self.sale.id}"

