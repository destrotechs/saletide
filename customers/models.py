from django.db import models
from companies.models import Company
from core.models import CustomUser
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
# from payments.models import BasePayment

class Customer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="customers")
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    phone = models.CharField(max_length=20)
    business_name = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    currency = models.CharField(max_length=255, blank=True, null=True)
    billing_name = models.CharField(max_length=255, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('company', 'email','phone')  # Ensure unique company,email and phone per customer

    def __str__(self):
        return f"{self.full_name} ({self.company.name})"
class CustomerAddress(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    city = models.CharField(blank=True,null=True,max_length=200)
    street = models.CharField(blank=True,null=True,max_length=200)
    country = models.CharField(max_length=200,default='KENYA')
    state = models.CharField(blank=True,null=True,max_length=200)
    zip_code = models.CharField(blank=True,null=True,max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.customer.full_name} - {self.city}"
    @property
    def formatted_address(self):
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}"

class CustomerVehicle(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="vehicles")
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField(blank=True, null=True)
    color = models.CharField(max_length=100,blank=True)
    plate_number = models.CharField(max_length=20)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('customer', 'plate_number')  # Ensure unique company,email and phone per customer


    def __str__(self):
        return f"{self.model} ({self.plate_number})"

class LoyaltyPoint(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="loyalty_points")
    points = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.customer.full_name} - {self.points} points"

class CustomerServiceRecord(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="service_records")
    vehicle = models.ForeignKey(CustomerVehicle, on_delete=models.CASCADE, null=True, blank=True)
    service = models.ForeignKey('services.Service', on_delete=models.CASCADE, null=True, blank=True)
    date_started = models.DateField(auto_now_add=True)
    date_completed = models.DateField()
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('customer','vehicle','service','date_started')  # Ensure unique customer, vehicle, service_name and date_started per record

    def __str__(self):
        return f"{self.service} - {self.customer.full_name}"

class CustomerRedemption(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="redemptions")
    points_used = models.PositiveIntegerField()
    date_redeemed = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.customer.full_name} - Redeemed {self.points_used} points"


from django.db import models
from django.utils import timezone


class CustomerAppointment(models.Model):
    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("Confirmed", "Confirmed"),
        ("In_Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
        ("No_Show", "No Show"),
    ]
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name="appointments")
    services = models.ManyToManyField(
        'services.Service',
        through='AppointmentService',
        related_name="appointments",blank=True
    )
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Scheduled")
    notes = models.TextField(blank=True, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-appointment_date', 'start_time']
        indexes = [
            models.Index(fields=['appointment_date', 'status']),
            models.Index(fields=['customer']),
        ]

    def __str__(self):
        try:
            # Get service names through the AppointmentService relationship
            appointment_services = self.appointmentservice_set.all()
            if appointment_services.exists():
                service_names = ", ".join([as_obj.service.name for as_obj in appointment_services])
            else:
                service_names = "No services"
            return f"{self.customer.full_name} - {service_names} on {self.appointment_date} at {self.start_time}"
        except Exception:
            # Fallback in case of any issues
            return f"Appointment {self.id} - {self.customer.full_name} on {self.appointment_date}"

    def get_total_duration(self):
        """Calculate total duration of all services"""
        try:
            total_minutes = sum(
                appointment_service.get_effective_duration()
                for appointment_service in self.appointmentservice_set.all()
            )
            return total_minutes
        except Exception:
            return 0

    def calculate_total_price(self):
        """Calculate total price of all services"""
        try:
            total = sum(
                appointment_service.get_effective_price()
                for appointment_service in self.appointmentservice_set.all()
            )
            return total
        except Exception:
            return 0

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Only update total_price if it's not already set and we have services
        if self.pk and (not self.total_price or self.total_price == 0):
            calculated_price = self.calculate_total_price()
            if calculated_price > 0:
                self.total_price = calculated_price
                super().save(update_fields=['total_price'])


class AppointmentService(models.Model):
    """Through model to store additional information per service in an appointment"""
    appointment = models.ForeignKey(CustomerAppointment, on_delete=models.CASCADE,blank=True)
    service = models.ForeignKey('services.Service', on_delete=models.CASCADE,blank=True)

    # Optional: Override service defaults for this specific appointment
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                help_text="Override service price for this appointment")
    duration = models.PositiveIntegerField(null=True, blank=True,
                                           help_text="Override service duration for this appointment (in minutes)")

    # Service-specific notes
    notes = models.TextField(blank=True, null=True)

    # Track completion status per service
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('appointment', 'service')
        ordering = ['id']

    def get_effective_price(self):
        """Get the price for this service (override or default)"""
        return self.price if self.price is not None else self.service.price

    def get_effective_duration(self):
        """Get the duration for this service (override or default)"""
        return self.duration if self.duration is not None else getattr(self.service, 'duration_minutes', 0)

    def __str__(self):
        return f"{self.service.name} for {self.appointment.customer.full_name}"
class PaymentStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    COMPLETED = "Completed", "Completed"
    FAILED = "Failed", "Failed"

# class CustomerPayment(BasePayment):
#     customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="payments")
#     amount = models.DecimalField(max_digits=10, decimal_places=2)
#     method = models.CharField(max_length=50, choices=[("paypal", "PayPal"), ("stripe", "Stripe"), ("mpesa", "MPESA")])
#     transaction_id = models.CharField(max_length=255, unique=True)
#     status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
#     created_at = models.DateTimeField(auto_now_add=True)
#
#     def __str__(self):
#         return f"{self.customer.full_name} - {self.method} - {self.amount} ({self.status})"

# @receiver(post_save, sender=CustomerServiceRecord)
# def notify_customer_service_completion(sender, instance, created, **kwargs):
#     """Notify customer via email when a service is completed."""
#     if created:
#         subject = f"Service Completed: {instance.service_name}"
#         message = f"Dear {instance.customer.full_name},\n\nYour service '{instance.service_name}' has been completed on {instance.date_completed}. Thank you for choosing us!"
#
#         send_mail(
#             subject,
#             message,
#             settings.DEFAULT_FROM_EMAIL,
#             [instance.customer.email],
#             fail_silently=False,
#         )


@receiver(post_save, sender=CustomerRedemption)
def notify_customer_redemption(sender, instance, created, **kwargs):
    """Notify customer when loyalty points are redeemed."""
    if created:
        subject = "Loyalty Points Redeemed"
        message = f"Dear {instance.customer.full_name},\n\nYou have successfully redeemed {instance.points_used} points. Thank you for your loyalty!"

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [instance.customer.email],
            fail_silently=False,
        )