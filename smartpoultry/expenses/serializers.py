from rest_framework import serializers
from .models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    distribution_date = serializers.DateField(source='inventory_distribution.date',read_only=True,default=None)
    distribution_reversed_at = serializers.DateTimeField(source='inventory_distribution.reversed_at',read_only=True,default=None)

    def validate(self, attrs):
        if self.instance and (self.instance.inventory_purchase_id or self.instance.inventory_distribution_id):
            raise serializers.ValidationError('Inventory costs are managed through inventory distributions.')
        return attrs

    def validate_branch(self, branch):
        request = self.context.get('request')
        if request and branch and branch.farm.owner_id != request.user.id:
            raise serializers.ValidationError('Select a branch from your farm.')
        return branch

    class Meta:
        model = Expense
        fields = ['id', 'branch', 'branch_name', 'expense_type', 'description', 'amount', 'date',
                  'category', 'notes', 'created_at', 'updated_at','inventory_purchase','inventory_distribution','distribution_date','distribution_reversed_at']
        read_only_fields = ['id', 'created_at', 'updated_at','inventory_purchase','inventory_distribution','distribution_date']
