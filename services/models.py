from django.db import models
from rest_framework.exceptions import ValidationError

from companies.models import Company, Employee
# from customers.models import Customer


class ItemType(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="item_types")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Service(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.IntegerField(null=True)
    # Changed from ForeignKey to ManyToManyField
    item_types = models.ManyToManyField(ItemType, related_name="services")
    tax_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted = models.BooleanField(default=False)
    requires_products = models.BooleanField(default=False)
    service_products = models.ManyToManyField('services.ServiceProductRequirement',related_name='products')
    points = models.PositiveIntegerField(default=1)
    def __str__(self):
        return self.name


class ServiceProductRequirement(models.Model):
    service = models.ForeignKey("Service", on_delete=models.CASCADE, related_name="inventory_requirements")
    inventory_item = models.ForeignKey("inventory.InventoryItem", on_delete=models.CASCADE, related_name="service_usages")
    quantity_required = models.PositiveIntegerField(help_text="Amount of inventory item needed per service")

    class Meta:
        unique_together = ('service', 'inventory_item')

    def clean(self):
        """Ensure the inventory item and service belong to the same company."""
        if self.service.company != self.inventory_item.company:
            raise ValidationError("Service and InventoryItem must belong to the same company.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity_required} {self.inventory_item.unit} of {self.inventory_item.name} for {self.service.name}"


# class Appointment(models.Model):
#     company = models.ForeignKey(Company, on_delete=models.CASCADE)
#     customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
#     service = models.ForeignKey(Service, on_delete=models.CASCADE)
#     employee = models.ForeignKey(Employee, on_delete=models.CASCADE, null=True, blank=True)
#     date_time = models.DateTimeField()
#     status = models.CharField(max_length=20, choices=[('Scheduled', 'Scheduled'), ('Completed', 'Completed')])
#
#     def __str__(self):
#         return f"{self.customer} - {self.service} on {self.date_time}"
