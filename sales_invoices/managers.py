from django.db import models
from django.db.models import Sum, Count
from django.utils.timezone import now
from datetime import timedelta

class SaleQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def this_month(self):
        today = now().date()
        first_day = today.replace(day=1)
        return self.active().filter(date__gte=first_day)

    def total_revenue(self):
        return self.active().aggregate(total=Sum('items__total'))['total'] or 0

    def total_sales_count(self):
        return self.active().count()

    def total_services(self):
        return self.active().filter(items__type='service').count()

    def total_products(self):
        return self.active().filter(items__type='product').count()

    def total_service_sale_amount(self):
        return self.active().filter(items__type='service').aggregate(
            total=Sum('items__total'))['total'] or 0

    def total_product_sale_amount(self):
        return self.active().filter(items__type='product').aggregate(
            total=Sum('items__total'))['total'] or 0

class SaleManager(models.Manager):
    def get_queryset(self):
        return SaleQuerySet(self.model, using=self._db)

    def dashboard_insights(self, company_id):
        qs = self.get_queryset().active().filter(company_id=company_id)
        this_month = qs.this_month()

        return {
            "total_sales": qs.total_sales_count(),
            "total_revenue": qs.total_revenue(),
            "monthly_sales": this_month.count(),
            "monthly_revenue": this_month.total_revenue(),
            "total_services": qs.total_services(),
            "total_products": qs.total_products(),
            "total_service_sale_amount": qs.total_service_sale_amount(),
            "total_product_sale_amount": qs.total_product_sale_amount(),
        }

