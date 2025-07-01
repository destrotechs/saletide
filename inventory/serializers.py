from rest_framework import serializers
from .models import InventoryCategory, InventoryItem


class InventoryCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryCategory
        fields = '__all__'


class InventoryItemSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=InventoryCategory.objects.all())
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = '__all__'

    def get_category_name(self,obj):
        return obj.category.name if obj.category else None