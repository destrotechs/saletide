from django.apps import AppConfig


class SalesInvoicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sales_invoices'

    def ready(self):
        import sales_invoices.signals
