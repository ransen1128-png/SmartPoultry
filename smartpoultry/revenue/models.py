from django.db import models
from django.conf import settings
from flocks.models import Flock
from core.models import Branch
from django.core.exceptions import ValidationError
from django.db import transaction


class Revenue(models.Model):
    """Revenue/income tracking."""
    REVENUE_TYPES = [
        ('eggs', 'Eggs'),
        ('meat', 'Meat'),
        ('birds', 'Birds'),
        ('manure', 'Manure'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='revenue_records', null=True, blank=True)
    branch = models.ForeignKey('core.Branch', on_delete=models.SET_NULL, related_name='revenue_records', null=True, blank=True)
    revenue_type = models.CharField(max_length=50, choices=REVENUE_TYPES)
    flock = models.ForeignKey(Flock, on_delete=models.SET_NULL, null=True, blank=True)
    production = models.ForeignKey('production.ProductionRecord', on_delete=models.RESTRICT, null=True, blank=True, related_name='revenue_sales')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, default='units')
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, editable=False)
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.production_id:
                from production.models import ProductionRecord
                # All sales from a batch serialize on the same production row.
                production = ProductionRecord.objects.select_for_update().get(pk=self.production_id)
                if production.user_id != self.user_id:
                    raise ValidationError({'production': 'Select production from your account.'})
                if production.flock.status != 'active' or (production.branch_id and production.branch.status != 'active'):
                    raise ValidationError({'production': 'Select production from an active flock and branch.'})
                sold = production.revenue_sales.exclude(pk=self.pk).aggregate(total=models.Sum('quantity'))['total'] or 0
                if self.quantity <= 0 or self.quantity > production.quantity-sold:
                    raise ValidationError({'quantity': f'Only {production.quantity-sold} available from this production record.'})
                if self.date < production.date:
                    raise ValidationError({'date': 'Sale date cannot be earlier than production date.'})
                self.branch_id, self.flock_id = production.branch_id, production.flock_id
                self.revenue_type = 'eggs' if production.product_type == 'eggs' else 'meat'
                self.unit = production.unit
            self.total_amount = self.quantity * self.price_per_unit
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.revenue_type.upper()} - {self.total_amount} ({self.date})"

    class Meta:
        ordering = ['branch__name', '-date', '-created_at']
