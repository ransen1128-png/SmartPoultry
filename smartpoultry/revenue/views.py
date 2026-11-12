from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from notifications.utils import create_activity_notification
from .models import Revenue
from .serializers import RevenueSerializer
from rest_framework.decorators import action
from rest_framework.response import Response


class RevenueViewSet(viewsets.ModelViewSet):
    """ViewSet for managing revenue."""
    serializer_class = RevenueSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='available-production')
    def available_production(self, request):
        from production.models import ProductionRecord
        from django.db.models import Sum, Value, DecimalField, F
        from django.db.models.functions import Coalesce
        records = ProductionRecord.objects.filter(user=request.user, flock__status='active').exclude(branch__status='inactive').exclude(flock__branch__status='inactive').select_related('branch','flock').annotate(
            _sold_quantity=Coalesce(Sum('revenue_sales__quantity'), Value(0), output_field=DecimalField()),
        ).annotate(_available=F('quantity')-F('_sold_quantity')).filter(_available__gt=0)
        return Response([{'id': record.pk, 'branch': record.branch_id, 'branch_name': record.branch.name if record.branch_id else 'Unassigned',
                          'flock': record.flock.flock_id, 'product': record.get_product_type_display(),
                          'revenue_type': 'eggs' if record.product_type == 'eggs' else 'meat',
                          'available_quantity': str(record.available_quantity), 'date': record.date.isoformat()} for record in records])

    def get_queryset(self):
        return Revenue.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        revenue = serializer.save(user=self.request.user)
        create_activity_notification(
            self.request.user,
            f"Successfully added {revenue.get_revenue_type_display().lower()} revenue",
            f"Recorded revenue of PHP {revenue.total_amount} from {revenue.quantity} {revenue.unit}.",
            revenue,
        )
