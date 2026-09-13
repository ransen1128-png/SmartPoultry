from django.db import models
from django.conf import settings
from flocks.models import Flock
from core.models import Branch


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
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, default='units')
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, editable=False)
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.price_per_unit
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.revenue_type.upper()} - {self.total_amount} ({self.date})"

    class Meta:
        ordering = ['branch__name', '-date', '-created_at']
