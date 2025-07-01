from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (ServiceViewSet, ServiceProductRequirementViewSet,ItemTypeViewSet) #AppointmentViewSet)

router = DefaultRouter()
router.register(r"services", ServiceViewSet, basename="service")
router.register(r"service-requirements", ServiceProductRequirementViewSet, basename="service-requirement")
# router.register(r"appointments", AppointmentViewSet, basename="appointment")
router.register(r"item-types", ItemTypeViewSet, basename="item-type")

urlpatterns = [
    path("", include(router.urls)),
]
