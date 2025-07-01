from rest_framework import serializers
from .models import Service, ServiceProductRequirement,ItemType
from inventory.models import InventoryItem

class ItemTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemType
        fields = "__all__"
        read_only_fields = ["created_at", "modified_at", "deleted_at"]
class ServiceProductRequirementSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        source='inventory_item',
        queryset=InventoryItem.objects.all()
    )
    quantity = serializers.IntegerField(source='quantity_required')

    class Meta:
        model = ServiceProductRequirement
        fields = ('product', 'quantity')


class ServiceSerializer(serializers.ModelSerializer):
    item_types = serializers.PrimaryKeyRelatedField(
        queryset=ItemType.objects.all(), many=True
    )
    service_products = ServiceProductRequirementSerializer(many=True, write_only=True)
    service_products_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Service
        fields = [
            'id', 'company', 'name', 'description', 'price',
            'duration_minutes', 'item_types', 'tax_rate',
            'requires_products', 'service_products','service_products_display','discount_rate'
        ]

    def create(self, validated_data):
        print("creating....123")
        item_types = validated_data.pop('item_types', [])
        service_products_data = validated_data.pop('service_products', [])

        service = Service.objects.create(**validated_data)
        service.item_types.set(item_types)

        for sp_data in service_products_data:
            ServiceProductRequirement.objects.create(service=service, **sp_data)

        return service

    def update(self, instance, validated_data):
        item_types = validated_data.pop('item_types', None)
        service_products_data = validated_data.pop('service_products', None)
        print("Item Types ",item_types)
        print("Service Products",service_products_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if item_types is not None:
            instance.item_types.set(item_types)

        if service_products_data is not None:
            seen = []
            for sp_data in service_products_data:
                inventory_item = sp_data['inventory_item']
                seen.append(inventory_item.id)

                ServiceProductRequirement.objects.update_or_create(
                    service=instance,
                    inventory_item=inventory_item,
                    defaults=sp_data
                )

            # Delete any that are no longer present
            instance.service_products.exclude(inventory_item__id__in=seen).delete()

        return instance
    def get_service_products_display(self,obj):
        products = ServiceProductRequirement.objects.filter(service_id=obj.id)

        return [{'product_id':product.inventory_item_id,'quantity_required':product.quantity_required,"unit_price":product.inventory_item.selling_unit_price} for product in products]

# class AppointmentSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Appointment
#         fields = "__all__"
