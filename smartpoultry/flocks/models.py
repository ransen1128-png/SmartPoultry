from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import Branch


class Flock(models.Model):
    """Flock/batch of poultry."""
    BREED_CHOICES = [
        ('layers', 'Layers'),
        ('broilers', 'Broilers'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('sold', 'Sold'),
        ('deceased', 'Deceased'),
        ('retired', 'Retired'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flocks', null=True, blank=True)
    branch = models.ForeignKey('core.Branch', on_delete=models.SET_NULL, related_name='flocks', null=True, blank=True)
    flock_id = models.CharField(max_length=100)
    breed = models.CharField(max_length=50, choices=BREED_CHOICES)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    date_added = models.DateField(auto_now_add=True)
    expected_production_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.flock_id} - {self.breed} ({self.quantity})"

    class Meta:
        ordering = ['branch__name', '-date_added', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'flock_id'], name='unique_flock_id_per_user'),
        ]
