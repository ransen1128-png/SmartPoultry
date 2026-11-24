from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from notifications.utils import create_activity_notification
from .models import Flock
from .numbering import next_flock_id
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
        user = get_user_model().objects.get(pk=self.request.user.pk)
        branch = serializer.validated_data.get('branch')
        # Each branch (and the main branch) numbers its own flocks; the primary key stays the global identifier.
        for attempt in range(3):
            flock_id = next_flock_id(user.pk, branch.pk if branch else None)
            try:
                with transaction.atomic():
                    flock = serializer.save(user=user, flock_id=flock_id)
                break
            except IntegrityError:
                # The branch unique constraint caught a concurrent writer; pick the next number.
                if attempt == 2:
                    raise ValidationError({'flock_id': 'A Flock ID could not be assigned. Please try again.'})
        create_activity_notification(
            self.request.user,
            f"Successfully added a new flock of {flock.get_breed_display().lower()}",
            f"{flock.quantity} {flock.get_breed_display().lower()} were added as flock {flock.display_label}.",
            flock,
        )
