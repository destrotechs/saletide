from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

class InventoryTransaction(models.Model):
    ADD = 'add'
    REMOVE = 'remove'
    TRANSACTION_TYPES = [
        (ADD, 'Addition'),
        (REMOVE, 'Removal'),
    ]

    item = models.ForeignKey('InventoryItem', on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    quantity = models.PositiveIntegerField()
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.transaction_type.capitalize()} {self.quantity} {self.item.unit} of {self.item.name} by {self.performed_by}"


class InventoryCategory(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="inventory_categories")
    name = models.CharField(max_length=255)
    is_deleted = models.BooleanField(default=False)  # Soft delete
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_company_category_name')
        ]



class InventoryItem(models.Model):
    UNIT_CHOICES = [
        ("pcs", "Pieces"),
        ("kg", "Kilograms"),
        ("ltr", "Liters"),
        ("m", "Meters"),
        ("box", "Box"),
    ]

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="inventory_items")
    category = models.ForeignKey(InventoryCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="items")
    name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=0)
    buying_unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="pcs")
    min_stock_level = models.PositiveIntegerField(default=5, help_text="Threshold for low stock alert")
    tax_rate = models.DecimalField(max_digits=10, decimal_places=2,default=0.0)
    discount_rate = models.DecimalField(max_digits=10, decimal_places=2,default=0.0)
    is_deleted = models.BooleanField(default=False)  # Soft delete
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "name")  # Prevent duplicate names per company

    def clean(self):
        """Ensure quantity and unit price are valid."""
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative.")
        if self.selling_unit_price < 0:
            raise ValidationError("Unit price cannot be negative.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.quantity} {self.unit} (Ksh {self.selling_unit_price})"

    def is_low_stock(self):
        """Check if stock is below threshold."""
        return self.quantity <= self.min_stock_level

    def reduce_stock(self, amount, user=None, notes=None):
        if amount > self.quantity:
            raise ValidationError(f"Not enough {self.name} in stock.")
        self.quantity -= amount
        self.save()
        InventoryTransaction.objects.create(
            item=self,
            transaction_type=InventoryTransaction.REMOVE,
            quantity=amount,
            performed_by=user,
            notes=notes
        )

    def increase_stock(self, amount, user=None, notes=None):
        self.quantity += amount
        self.save()
        InventoryTransaction.objects.create(
            item=self,
            transaction_type=InventoryTransaction.ADD,
            quantity=amount,
            performed_by=user,
            notes=notes
        )
