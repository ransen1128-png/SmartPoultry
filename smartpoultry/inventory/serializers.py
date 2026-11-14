from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import Inventory, InventoryDistribution, FeedType


class FeedTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedType
        fields = ['id', 'name', 'unit', 'cost_per_unit']


class InventorySerializer(serializers.ModelSerializer):
    is_low_stock=serializers.SerializerMethodField()
    total_content=serializers.DecimalField(max_digits=22,decimal_places=5,read_only=True,allow_null=True)

    def get_is_low_stock(self,item):
        return item.minimum_stock is not None and item.quantity<=item.minimum_stock

    def validate(self,attrs):
        for field in ('quantity','cost_per_unit','minimum_stock'):
            if attrs.get(field) is not None and attrs[field]<0:
                raise serializers.ValidationError({field:'Must not be negative.'})
        size=attrs.get('package_size',getattr(self.instance,'package_size',None))
        content=attrs.get('content_unit',getattr(self.instance,'content_unit','')).strip()
        if (size is None)!=(not content):raise serializers.ValidationError({'package_size':'Enter both package size and content unit, or leave both empty for bulk stock.'})
        if size is not None and size<=0:raise serializers.ValidationError({'package_size':'Package size must be greater than zero.'})
        if self.instance and self.instance.distributions.exists() and 'unit' in attrs and attrs['unit']!=self.instance.unit and size is None:
            raise serializers.ValidationError({'unit':'Enter explicit package size and content unit to correct a package label after distributions. Quantities and costs are not converted.'})
        return attrs

    class Meta:
        model = Inventory
        fields = ['id', 'item_type', 'name', 'quantity', 'unit', 'cost_per_unit', 
                  'total_value', 'date_added', 'last_updated', 'notes','minimum_stock','is_low_stock','package_size','content_unit','total_content']
        read_only_fields = ['id', 'total_value', 'last_updated']


class InventoryDistributionSerializer(serializers.ModelSerializer):
    stock_warning = serializers.CharField(read_only=True,default=None)
    item_name = serializers.CharField(source='inventory.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    unit = serializers.CharField(source='unit_snapshot', read_only=True)
    flock_name = serializers.CharField(source='flock.flock_id',read_only=True,default=None)
    expense_id = serializers.IntegerField(source='expense.pk', read_only=True, default=None)
    expense_amount = serializers.DecimalField(source='expense.amount',max_digits=15,decimal_places=2,read_only=True,default=None)
    cost_per_unit = serializers.DecimalField(source='inventory.purchase_cost_per_unit',max_digits=10,decimal_places=2,read_only=True)

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
        fields = ['id', 'inventory', 'item_name', 'branch', 'branch_name', 'quantity', 'unit', 'date', 'created_at','expense_id','expense_amount','cost_per_unit','flock','flock_name','cost_snapshot','reversed_at','reversal_reason','package_size_snapshot','content_unit_snapshot','stock_warning']
        read_only_fields = ['id', 'item_name', 'branch_name', 'unit', 'created_at','cost_snapshot','reversed_at','reversal_reason','package_size_snapshot','content_unit_snapshot']
