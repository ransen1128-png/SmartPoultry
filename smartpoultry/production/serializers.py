from rest_framework import serializers
from .models import ProductionRecord, MortalityRecord, BreedInformation, HealthRecord


class ProductionRecordSerializer(serializers.ModelSerializer):
    def create(self,validated_data):
        from django.core.exceptions import ValidationError as ModelError
        try:return super().create(validated_data)
        except ModelError as error:raise serializers.ValidationError(error.message_dict if hasattr(error,'message_dict') else error.messages)

    def update(self,instance,validated_data):
        from django.core.exceptions import ValidationError as ModelError
        try:return super().update(instance,validated_data)
        except ModelError as error:raise serializers.ValidationError(error.message_dict if hasattr(error,'message_dict') else error.messages)

    branch_name = serializers.CharField(source='branch.name', read_only=True)
    sold_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    available_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    def validate_flock(self, flock):
        request = self.context.get('request')
        if request and flock.user_id != request.user.id:
            raise serializers.ValidationError('Select one of your own flocks.')
        if flock.status != 'active' or (flock.branch_id and flock.branch.status != 'active'):
            raise serializers.ValidationError('Select an active flock from an active branch.')
        if not self.instance and flock.quantity<=0:
            raise serializers.ValidationError('This flock has no live chicken remaining.')
        return flock

    def validate_branch(self, branch):
        request = self.context.get('request')
        if request and branch and branch.farm.owner_id != request.user.id:
            raise serializers.ValidationError('Select a branch from your farm.')
        return branch

    def validate(self, attrs):
        flock = attrs.get('flock', getattr(self.instance, 'flock', None))
        branch = attrs.get('branch', getattr(self.instance, 'branch', None))
        product_type = attrs.get('product_type', getattr(self.instance, 'product_type', None))
        egg_size=attrs.get('egg_size',getattr(self.instance,'egg_size',''))
        if product_type=='eggs' and not egg_size and (self.instance is None or self.instance.egg_size):
            raise serializers.ValidationError({'egg_size':'Choose Small, Medium or Large for these eggs.'})
        if product_type!='eggs' and egg_size:
            raise serializers.ValidationError({'egg_size':'Egg size applies only to egg production.'})
        if self.instance and self.instance.revenue_sales.exists():
            if attrs.get('quantity', self.instance.quantity) < self.instance.sold_quantity:
                raise serializers.ValidationError({'quantity': 'Quantity cannot be below the amount already sold.'})
            for field in ('flock','branch','product_type','egg_size','unit','date'):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError({field: 'Production details with sales history cannot be changed.'})
        if flock and (flock.status != 'active' or (flock.branch_id and flock.branch.status != 'active')):
            raise serializers.ValidationError({'flock': 'Select an active flock from an active branch.'})
        if flock and flock.branch_id != (branch.pk if branch else None):
            raise serializers.ValidationError({
                'flock': 'Select a flock from the selected branch.'
            })
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
        fields = ['id', 'branch', 'branch_name', 'flock', 'product_type', 'egg_size', 'quantity', 'sold_quantity', 'available_quantity', 'unit', 'date', 'notes', 'created_at']
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
        branch = attrs.get('branch', getattr(self.instance, 'branch', None))
        if flock.branch_id != (branch.pk if branch else None):
            raise serializers.ValidationError({'flock': 'Select a flock from the selected branch.'})
        if flock.user_id != self.context['request'].user.pk or flock.status != 'active' or (flock.branch_id and flock.branch.status != 'active'):
            raise serializers.ValidationError({'flock': 'Select an active flock from your active branches.'})

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
