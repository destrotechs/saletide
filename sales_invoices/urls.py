from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SaleViewSet, InvoiceViewSet,PaymentView

# Create a router for Sale and Invoice viewsets
router = DefaultRouter()
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'invoices', InvoiceViewSet, basename='invoice')

urlpatterns = [
    path('', include(router.urls)),
    path('payments/', PaymentView.as_view(),name="create_payment"),
]
