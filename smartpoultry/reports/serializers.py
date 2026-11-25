from rest_framework import serializers
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'End date must be on or after the start date.'})
        return attrs

    class Meta:
        model = Report
        fields = ['id', 'report_type', 'title', 'start_date', 'end_date', 
                  'summary', 'generated_at', 'updated_at']
        read_only_fields = ['id', 'generated_at', 'updated_at']
