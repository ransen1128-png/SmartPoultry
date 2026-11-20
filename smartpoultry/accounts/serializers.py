from rest_framework import serializers
from .models import UserProfile, UserRole
from core.contact_validation import PHONE_ERROR, valid_contact_phone


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'name', 'description', 'is_custom']


class UserProfileSerializer(serializers.ModelSerializer):
    def validate_phone(self, value):
        if value and not valid_contact_phone(value):
            raise serializers.ValidationError(PHONE_ERROR)
        return value

    def get_fields(self):
        fields=super().get_fields()
        request=self.context.get('request')
        if request and not (request.user.is_staff or request.user.is_superuser):
            for name in ('role','farm','is_active_user'):fields[name].read_only=True
        return fields

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone', 
                  'role', 'farm', 'is_active_user']
        read_only_fields = ['id']
