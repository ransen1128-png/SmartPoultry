from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from notifications.utils import create_activity_notification
from .models import Flock
from .serializers import FlockSerializer
from rest_framework.exceptions import ValidationError


class FlockViewSet(viewsets.ModelViewSet):
    """ViewSet for managing flocks."""
    serializer_class = FlockSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Flock.objects.filter(user=self.request.user)

    def perform_destroy(self,instance):
        from production.models import MortalityRecord
        from expenses.models import Expense
        if instance.in_history or Expense.objects.filter(flock_purchase=instance).exists() or instance.production_records.exists() or MortalityRecord.objects.filter(flock=instance).exists() or instance.inventory_distributions.exists() or instance.revenue_set.exists() or instance.health_records.exists():
            raise ValidationError('This flock has recorded activity. Its history must be retained; mark it sold or inactive instead.')
        instance.delete()

    def perform_create(self, serializer):
        flock = serializer.save(user=self.request.user)
        create_activity_notification(
            self.request.user,
            f"Successfully added a new flock of {flock.get_breed_display().lower()}",
            f"{flock.quantity} {flock.get_breed_display().lower()} were added as flock {flock.flock_id}.",
            flock,
        )
