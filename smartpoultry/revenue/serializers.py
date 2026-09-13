from rest_framework import serializers
from .models import Revenue


class RevenueSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    def validate_flock(self, flock):
        request = self.context.get('request')
        if flock and request and flock.user_id != request.user.id:
            raise serializers.ValidationError('Select one of your own flocks.')
        return flock

    def validate_branch(self, branch):
        request = self.context.get('request')
        if request and branch and branch.farm.owner_id != request.user.id:
            raise serializers.ValidationError('Select a branch from your farm.')
        return branch

    class Meta:
        model = Revenue
        fields = ['id', 'branch', 'branch_name', 'revenue_type', 'flock', 'quantity', 'unit', 'price_per_unit',
                  'total_amount', 'date', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_amount', 'created_at', 'updated_at']
