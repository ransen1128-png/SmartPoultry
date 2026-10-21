from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import Inventory, InventoryDistribution, FeedType


class FeedTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedType
        fields = ['id', 'name', 'unit', 'cost_per_unit']


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = ['id', 'item_type', 'name', 'quantity', 'unit', 'cost_per_unit', 
                  'total_value', 'date_added', 'last_updated', 'notes']
        read_only_fields = ['id', 'total_value', 'date_added', 'last_updated']


class InventoryDistributionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='inventory.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    unit = serializers.CharField(source='inventory.unit', read_only=True)

    def validate_inventory(self, inventory):
        request = self.context.get('request')
        if request and inventory.user_id != request.user.id:
            raise serializers.ValidationError('Select an inventory item from your account.')
        return inventory

    def validate_branch(self, branch):
        request = self.context.get('request')
        if request and branch.farm.owner_id != request.user.id:
            raise serializers.ValidationError('Select a branch from your farm.')
        return branch

    def create(self, validated_data):
        try:
            return InventoryDistribution.objects.create(**validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict if hasattr(error, 'message_dict') else error.messages)

    class Meta:
        model = InventoryDistribution
        fields = ['id', 'inventory', 'item_name', 'branch', 'branch_name', 'quantity', 'unit', 'date', 'created_at']
        read_only_fields = ['id', 'item_name', 'branch_name', 'unit', 'created_at']
