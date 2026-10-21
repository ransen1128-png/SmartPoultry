from rest_framework import serializers
from .models import Flock


class FlockSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    def validate_branch(self, branch):
        request = self.context.get('request')
        if request and branch and branch.farm.owner_id != request.user.id:
            raise serializers.ValidationError('Select a branch from your farm.')
        return branch

    def validate_flock_id(self, flock_id):
        request = self.context.get('request')
        if not request:
            return flock_id

        branch = self.initial_data.get('branch', getattr(self.instance, 'branch_id', None))
        queryset = Flock.objects.filter(user=request.user, flock_id=flock_id, branch_id=branch)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('This flock ID is already used in this branch.')
        return flock_id

    class Meta:
        model = Flock
        fields = ['id', 'branch', 'branch_name', 'flock_id', 'breed', 'quantity', 'status', 'date_added',
                  'expected_production_date', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
