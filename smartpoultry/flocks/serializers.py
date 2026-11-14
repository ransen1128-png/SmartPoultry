from rest_framework import serializers
from .models import Flock


class FlockSerializer(serializers.ModelSerializer):
    in_history = serializers.BooleanField(read_only=True)
    history_reason = serializers.CharField(read_only=True)
    acquisition_source_display = serializers.CharField(source='get_acquisition_source_display',read_only=True)
    purchase_total = serializers.DecimalField(max_digits=15,decimal_places=2,read_only=True)
    purchase_expense_id = serializers.IntegerField(source='purchase_expense.pk',read_only=True,default=None)
    ready_from = serializers.DateField(read_only=True)
    readiness_window_end = serializers.DateField(read_only=True)

    def create(self,validated_data):
        from django.core.exceptions import ValidationError as ModelError
        try:return super().create(validated_data)
        except ModelError as error:raise serializers.ValidationError(error.message_dict if hasattr(error,'message_dict') else error.messages)

    def validate_quantity(self,value):
        if value<0:raise serializers.ValidationError('Quantity cannot be negative.')
        return value

    def update(self,instance,validated_data):
        from django.core.exceptions import ValidationError as ModelError
        from django.db import transaction
        with transaction.atomic():
            instance=Flock.objects.select_for_update(of=('self',)).get(pk=instance.pk)
            if 'status' in validated_data and validated_data['status']!=instance.status:instance.auto_sold=False
            try:return super().update(instance,validated_data)
            except ModelError as error:raise serializers.ValidationError(error.message_dict if hasattr(error,'message_dict') else error.messages)
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    def validate(self, attrs):
        from django.utils import timezone
        placement=attrs.get('placement_date',getattr(self.instance,'placement_date',None))
        breed=attrs.get('breed',getattr(self.instance,'breed',None))
        if breed=='broilers' and not placement and (self.instance is None or self.instance.placement_date):
            raise serializers.ValidationError({'placement_date':'Enter the broiler delivery / hatch date. Harvest and sale start after 42 days.'})
        if placement and placement>timezone.localdate():
            raise serializers.ValidationError({'placement_date':'Delivery / hatch date cannot be in the future.'})
        branch = attrs.get('branch', getattr(self.instance, 'branch', None))
        status = attrs.get('status', getattr(self.instance, 'status', 'active'))
        if branch and branch.status != 'active' and status == 'active':
            raise serializers.ValidationError({'branch': 'Activate this branch before activating its flocks.'})
        for field in ('purchase_amount','delivery_cost'):
            if attrs.get(field,0)<0:raise serializers.ValidationError({field:'Cost cannot be negative.'})
        return attrs

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
        if branch in (None,''):branch=None
        elif not str(branch).isdigit():return flock_id
        queryset = Flock.objects.filter(user=request.user, flock_id=flock_id, branch_id=branch)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('This flock ID is already used in this branch.')
        return flock_id

    class Meta:
        model = Flock
        fields = ['id', 'branch', 'branch_name', 'flock_id', 'breed', 'quantity', 'status', 'in_history','history_reason','date_added',
                  'expected_production_date', 'notes', 'created_at', 'updated_at','acquisition_source','acquisition_source_display','purchase_amount','delivery_cost','purchase_date','supplier','purchase_total','purchase_expense_id','placement_date','ready_from','readiness_window_end']
        read_only_fields = ['id', 'created_at', 'updated_at']
