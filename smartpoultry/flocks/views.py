from django.contrib.auth import get_user_model
from django.db import transaction
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

    @transaction.atomic
    def perform_create(self, serializer):
        user = get_user_model().objects.select_for_update().get(pk=self.request.user.pk)
        existing_ids = set(self.get_queryset().values_list('flock_id', flat=True))
        flock_id = next((f'{number:02d}' for number in range(1, 101)
                         if f'{number:02d}' not in existing_ids and str(number) not in existing_ids), None)
        if flock_id is None:
            raise ValidationError({'flock_id': 'All Flock IDs from 01 to 100 are already in use.'})
        flock = serializer.save(user=user, flock_id=flock_id)
        create_activity_notification(
            self.request.user,
            f"Successfully added a new flock of {flock.get_breed_display().lower()}",
            f"{flock.quantity} {flock.get_breed_display().lower()} were added as flock {flock.flock_id}.",
            flock,
        )
