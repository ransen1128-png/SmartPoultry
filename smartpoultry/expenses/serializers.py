from rest_framework import serializers
from .models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    def create(self,validated_data):
        from django.core.exceptions import ValidationError as ModelError
        try:return super().create(validated_data)
        except ModelError as error:raise serializers.ValidationError(error.message_dict if hasattr(error,'message_dict') else error.messages)

    def update(self,instance,validated_data):
        from django.core.exceptions import ValidationError as ModelError
        try:return super().update(instance,validated_data)
        except ModelError as error:raise serializers.ValidationError(error.message_dict if hasattr(error,'message_dict') else error.messages)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    distribution_date = serializers.DateField(source='inventory_distribution.date',read_only=True,default=None)
    distribution_reversed_at = serializers.DateTimeField(source='inventory_distribution.reversed_at',read_only=True,default=None)
    item_quantity = serializers.DecimalField(source='inventory_distribution.quantity',max_digits=10,decimal_places=2,read_only=True,default=None)
    item_unit = serializers.CharField(source='inventory_distribution.unit_snapshot',read_only=True,default=None)
    item_unit_cost = serializers.DecimalField(source='inventory_distribution.inventory.purchase_cost_per_unit',max_digits=10,decimal_places=2,read_only=True,default=None)
    item_package_size = serializers.DecimalField(source='inventory_distribution.package_size_snapshot',max_digits=10,decimal_places=3,read_only=True,default=None)
    item_content_unit = serializers.CharField(source='inventory_distribution.content_unit_snapshot',read_only=True,default=None)

    def validate(self, attrs):
        if self.instance and (self.instance.inventory_purchase_id or self.instance.inventory_distribution_id or self.instance.flock_purchase_id):
            raise serializers.ValidationError('This expense is managed through its inventory distribution or flock purchase.')
        from django.core.exceptions import ValidationError as ModelError
        values={field:attrs.get(field,getattr(self.instance,field,None)) for field in ('expense_type','branch','description','amount','return_quantity','return_unit','return_item_name')}
        for field in ('description','return_unit','return_item_name'):values[field]=values[field] or ''
        try:Expense(**values).clean()
        except ModelError as error:raise serializers.ValidationError(error.message_dict if hasattr(error,'message_dict') else {'non_field_errors':error.messages})
        return attrs

    def validate_branch(self, branch):
        request = self.context.get('request')
        if request and branch and branch.farm.owner_id != request.user.id:
            raise serializers.ValidationError('Select a branch from your farm.')
        return branch

    class Meta:
        model = Expense
        fields = ['id', 'branch', 'branch_name', 'expense_type', 'description', 'amount', 'date',
                  'category', 'notes', 'created_at', 'updated_at','inventory_purchase','inventory_distribution','distribution_date','distribution_reversed_at','flock_purchase',
                  'item_quantity','item_unit','item_unit_cost','item_package_size','item_content_unit','return_quantity','return_unit','return_item_name']
        read_only_fields = ['id', 'created_at', 'updated_at','inventory_purchase','inventory_distribution','distribution_date','flock_purchase']
