from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet,
    CustomerVehicleViewSet,
    LoyaltyPointViewSet,
    CustomerServiceRecordViewSet,
    CustomerRedemptionViewSet,
    CustomerAppointmentViewSet,
# CustomerPaymentViewSet,
CustomerNotificationAPI
)

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename="customer")
router.register(r'vehicles', CustomerVehicleViewSet, basename="vehicle")
router.register(r'loyalty-points', LoyaltyPointViewSet, basename="loyalty-point")
router.register(r'service-records', CustomerServiceRecordViewSet, basename="service-record")
router.register(r'redemptions', CustomerRedemptionViewSet, basename="redemption")
router.register(r'appointments', CustomerAppointmentViewSet, basename="appointment")
# router.register(r'payments', CustomerPaymentViewSet)


urlpatterns = [
    path("", include(router.urls)),
    path("notifications/",CustomerNotificationAPI.as_view(),name="customer-notifications")
]
