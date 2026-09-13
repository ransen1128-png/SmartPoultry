from rest_framework import serializers
from .models import ProductionRecord, MortalityRecord, BreedInformation, HealthRecord


class ProductionRecordSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    def validate_flock(self, flock):
        request = self.context.get('request')
        if request and flock.user_id != request.user.id:
            raise serializers.ValidationError('Select one of your own flocks.')
        return flock

    def validate_branch(self, branch):
        request = self.context.get('request')
        if request and branch and branch.farm.owner_id != request.user.id:
            raise serializers.ValidationError('Select a branch from your farm.')
        return branch

    def validate(self, attrs):
        flock = attrs.get('flock', getattr(self.instance, 'flock', None))
        product_type = attrs.get('product_type', getattr(self.instance, 'product_type', None))
        expected_product = {
            'layers': 'eggs',
            'broilers': 'meat_ready',
        }.get(flock.breed if flock else None)
        if expected_product and product_type != expected_product:
            raise serializers.ValidationError({
                'product_type': 'Layers can only use Eggs; broilers can only use Meat Ready.'
            })
        return attrs

    class Meta:
        model = ProductionRecord
        fields = ['id', 'branch', 'branch_name', 'flock', 'product_type', 'quantity', 'unit', 'date', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']


class MortalityRecordSerializer(serializers.ModelSerializer):
    flock_id_display = serializers.CharField(source='flock.flock_id', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    def validate_branch(self, branch):
        request = self.context.get('request')
        if request and branch and branch.farm.owner_id != request.user.id:
            raise serializers.ValidationError('Select a branch from your farm.')
        return branch

    class Meta:
        model = MortalityRecord
        fields = [
            'id',
            'branch',
            'branch_name',
            'flock',
            'flock_id_display',
            'quantity',
            'reason',
            'date',
            'description',
            'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_flock(self, flock):
        request = self.context.get('request')
        if request and flock.user_id != request.user.id:
            raise serializers.ValidationError('Select one of your own flocks.')
        return flock

    def validate(self, attrs):
        flock = attrs.get('flock', getattr(self.instance, 'flock', None))
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', None))
        if flock is None or quantity is None:
            return attrs

        if quantity <= 0:
            raise serializers.ValidationError({'quantity': 'Mortality quantity must be greater than zero.'})

        available_quantity = flock.quantity
        if self.instance and self.instance.flock_quantity_applied and self.instance.flock_id == flock.id:
            available_quantity += self.instance.quantity

        if quantity > available_quantity:
            raise serializers.ValidationError({
                'quantity': f'Mortality quantity cannot exceed the selected flock quantity ({available_quantity}).'
            })
        return attrs


class BreedInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BreedInformation
        fields = ['id', 'name', 'type', 'egg_production_per_year', 'growth_period_days', 
                  'average_weight_kg', 'feed_consumption_daily_kg', 'lifespan_years', 'characteristics']
        read_only_fields = ['id']


class HealthRecordSerializer(serializers.ModelSerializer):
    def validate_flock(self, flock):
        request = self.context.get('request')
        if request and flock.user_id != request.user.id:
            raise serializers.ValidationError('Select one of your own flocks.')
        return flock

    class Meta:
        model = HealthRecord
        fields = ['id', 'flock', 'health_status', 'disease_name', 'treatment', 'medication', 
                  'vaccination_name', 'date', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']
