from rest_framework import serializers
from .models import Flock


class FlockSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    def validate_branch(self, branch):
        request = self.context.get('request')
        if request and branch and branch.farm.owner_id != request.user.id:
            raise serializers.ValidationError('Select a branch from your farm.')
        return branch

    class Meta:
        model = Flock
        fields = ['id', 'branch', 'branch_name', 'flock_id', 'breed', 'quantity', 'status', 'date_added',
                  'expected_production_date', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
