from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomerServiceRecord, LoyaltyPoint
from .models import CustomerAppointment
from .utilities import send_email,send_welcome_email,create_html_template,send_notification_email
# from django.core.mail import send_mail
# from django.conf import settings
# @receiver(post_save, sender=CustomerServiceRecord)
# def update_loyalty_points(sender, instance, created, **kwargs):
#     if created:
#         points = 10  # Example: Earn 10 points per service
#         loyalty, _ = LoyaltyPoint.objects.get_or_create(customer=instance.customer)
#         loyalty.points += points
#         loyalty.save()
#
#
# # @receiver(post_save, sender=CustomerPayment)
# # def send_payment_notification(sender, instance, **kwargs):
# #     """Notify customer via email when payment is completed or failed."""
# #     if instance.status in ["Completed", "Failed"]:
# #         subject = f"Payment {instance.status}"
# #         message = f"Dear {instance.customer.full_name},\n\nYour payment of {instance.amount} via {instance.method} is now marked as '{instance.status}'. Transaction ID: {instance.transaction_id}."
# #
# #         send_mail(
# #             subject,
# #             message,
# #             settings.DEFAULT_FROM_EMAIL,
# #             [instance.customer.email],
# #             fail_silently=False,
# #         )
@receiver(post_save, sender=CustomerAppointment)
def send_payment_notification(sender, instance, **kwargs):
    """Notify customer via email when payment is completed or failed."""
    message = f"Dear Customer, you have scheduled services on {instance.appointment_date} at {instance.start_time}. Please keep time."
    html_template = create_html_template("Scheduled Appointment",message)
    send_notification_email(instance.customer.email,"Scheduled Appointment",message)