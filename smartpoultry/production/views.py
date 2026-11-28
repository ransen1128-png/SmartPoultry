from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from notifications.utils import create_activity_notification
from .models import BreedInformation, MortalityRecord, ProductionRecord
from .serializers import BreedInformationSerializer, MortalityRecordSerializer, ProductionRecordSerializer


class ProductionRecordViewSet(viewsets.ModelViewSet):
    """ViewSet for production records."""
    serializer_class = ProductionRecordSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError
        if instance.revenue_sales.exists():
            raise ValidationError('Production with sales history cannot be deleted.')
        instance.delete()

    def get_queryset(self):
        return ProductionRecord.objects.filter(user=self.request.user).exclude(flock__status='inactive').exclude(branch__status='inactive').exclude(flock__branch__status='inactive')

    def perform_create(self, serializer):
        record = serializer.save(user=self.request.user)
        create_activity_notification(
            self.request.user,
            f"Successfully added {record.get_product_type_display().lower()} production record",
            f"Recorded {record.quantity:g} {record.unit} for flock {record.flock.display_label} on {record.date}.",
            record,
        )


class MortalityRecordViewSet(viewsets.ModelViewSet):
    """ViewSet for mortality records."""
    serializer_class = MortalityRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MortalityRecord.objects.filter(user=self.request.user).exclude(flock__status='inactive').exclude(branch__status='inactive').exclude(flock__branch__status='inactive')

    def perform_create(self, serializer):
        record = serializer.save(user=self.request.user)
        record.flock.refresh_from_db()
        create_activity_notification(
            self.request.user,
            "Successfully added mortality record",
            (
                f"Recorded {record.quantity} mortality for flock {record.flock.display_label} due to "
                f"{record.get_reason_display().lower()}."
            ),
            record,
        )


class BreedInformationViewSet(viewsets.ModelViewSet):
    """Breeds shared by every account: owners read them, administrators maintain them."""
    queryset = BreedInformation.objects.order_by('pk')
    serializer_class = BreedInformationSerializer

    def get_permissions(self):
        return [IsAuthenticated()] if self.action in ('list', 'retrieve') else [IsAdminUser()]
