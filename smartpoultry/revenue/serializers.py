from rest_framework import serializers
from .models import Revenue
from django.core.exceptions import ValidationError as DjangoValidationError
from production.models import ProductionRecord


class RevenueOrderItemSerializer(serializers.Serializer):
    production = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    price_per_unit = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)


class RevenueOrderSerializer(serializers.Serializer):
    buyer_name = serializers.CharField(max_length=255)
    buyer_contact = serializers.CharField(max_length=255, required=False, allow_blank=True)
    buyer_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    order_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    date = serializers.DateField()
    items = RevenueOrderItemSerializer(many=True, allow_empty=False, max_length=50)


class RevenueSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    revenue_type_display = serializers.CharField(source='get_revenue_type_display',read_only=True)
    egg_size = serializers.CharField(source='production.egg_size',read_only=True,default=None)
    egg_size_label = serializers.CharField(source='production.get_egg_size_display',read_only=True,default=None)
    production = serializers.PrimaryKeyRelatedField(queryset=ProductionRecord.objects.all(), required=False, allow_null=True)

    def validate(self, attrs):
        if self.instance is None and not attrs.get('buyer_name','').strip():
            raise serializers.ValidationError({'buyer_name':'Enter the buyer name for this sale.'})
        if 'buyer_name' in attrs and not attrs['buyer_name'].strip():
            raise serializers.ValidationError({'buyer_name':'Buyer name cannot be empty.'})
        production = attrs.get('production', getattr(self.instance, 'production', None))
        if production is None:
            raise serializers.ValidationError({'production': 'Select available production stock.'})
        if production.user_id != self.context['request'].user.pk:
            raise serializers.ValidationError({'production': 'Select production from your account.'})
        attrs.update(branch=production.branch, flock=production.flock,
                     revenue_type='eggs' if production.product_type == 'eggs' else 'meat', unit=production.unit)
        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict)

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict)

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
        fields = ['id', 'production', 'branch', 'branch_name', 'revenue_type','revenue_type_display', 'flock', 'quantity', 'unit', 'price_per_unit',
                  'total_amount', 'date', 'notes', 'created_at', 'updated_at','buyer_name','buyer_contact','buyer_address','order_number','transaction_number','egg_size','egg_size_label']
        read_only_fields = ['id', 'total_amount', 'created_at', 'updated_at','transaction_number']
        extra_kwargs = {'revenue_type': {'required': False}, 'price_per_unit': {'min_value': 0}, 'quantity': {'min_value': 0.01}}
