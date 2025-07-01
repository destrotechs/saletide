from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InventoryCategoryViewSet, InventoryItemViewSet

router = DefaultRouter()
router.register(r"inventory-categories", InventoryCategoryViewSet, basename="inventory-category")
router.register(r"inventory-items", InventoryItemViewSet, basename="inventory-item")

urlpatterns = [
    path("", include(router.urls)),
]
