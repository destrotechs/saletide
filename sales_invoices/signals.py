import decimal

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from sales_invoices.models import Sale, SaleItem, SaleItemEmployee
from companies.models import EmployeeCommissionSetting, EmployeeCommission
from customers.models import CustomerServiceRecord, LoyaltyPoint


@receiver(post_save, sender=SaleItemEmployee)
def handle_sale_item_employee_save(sender, instance, created, **kwargs):
    if created:
        update_commissions_for_sale_item(instance.sale_item)

def update_commissions_for_sale_item(sale_item):
    """Ensure commissions are correctly set for all employees assigned to this sale item."""
    # Remove previous commissions for this sale_item
    EmployeeCommission.objects.filter(sale_item=sale_item).delete()

    # Only calculate commissions for 'service' sale items
    if sale_item.type != 'service' or not sale_item.service:
        return

    for assignment in sale_item.assigned_employees.all():
        employee = assignment.employee
        try:
            setting = EmployeeCommissionSetting.objects.get(
                employee=employee,
                service=sale_item.service
            )
            commission_amount = (setting.commission_percentage / 100) * decimal.Decimal(sale_item.amount)
        except EmployeeCommissionSetting.DoesNotExist:
            commission_amount = 0

        if commission_amount > 0:
            EmployeeCommission.objects.create(
                sale_item=sale_item,
                employee=employee,
                commission_amount=commission_amount
            )

@receiver(post_save, sender=SaleItem)
def handle_sale_item_save(sender, instance, created, **kwargs):
    if created:
        create_customer_service_record(instance)

def create_customer_service_record(sale_item):
    print("Running service record signal...")
    sale = sale_item.sale
    if sale.customer and sale.vehicle and sale_item.type == 'service' and sale_item.service:
        try:
            record = CustomerServiceRecord.objects.create(
                customer=sale.customer,
                vehicle=sale.vehicle,
                service=sale_item.service,
                date_started=sale.date,
                date_completed=sale.date,
            )
            print("Service record created:", record)
            if sale.customer:
                customer_points = LoyaltyPoint.objects.filter(customer=sale.customer).first()
                LoyaltyPoint.objects.create(
                    customer = sale.customer,
                    points = (customer_points.points if customer_points else 0) + sale_item.service.points
                )
        except Exception:
            import traceback
            print("Error occurred while creating service record")
            traceback.print_exc()