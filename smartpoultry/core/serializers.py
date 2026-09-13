from rest_framework import serializers
from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            'id', 'farm', 'name', 'location', 'address', 'contact_number', 'description', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')
