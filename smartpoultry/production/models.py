from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from flocks.models import Flock
from core.models import Branch


class ProductionRecord(models.Model):
    """Daily production records for flocks."""
    PRODUCT_TYPES = [
        ('eggs', 'Eggs'),
        ('meat_ready', 'Meat Ready'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='production_records', null=True, blank=True)
    branch = models.ForeignKey('core.Branch', on_delete=models.SET_NULL, related_name='production_records', null=True, blank=True)
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='production_records')
    product_type = models.CharField(max_length=50, choices=PRODUCT_TYPES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, default='units')
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.flock} - {self.product_type} ({self.date})"
    
    class Meta:
        ordering = ['branch__name', '-date', '-created_at']
        unique_together = ('flock', 'product_type', 'date')


class MortalityRecord(models.Model):
    """Mortality records for flocks."""
    MORTALITY_REASONS = [
        ('disease', 'Disease'),
        ('predation', 'Predation'),
        ('stress', 'Stress'),
        ('accident', 'Accident'),
        ('age', 'Age'),
        ('unknown', 'Unknown'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mortality_records', null=True, blank=True)
    branch = models.ForeignKey('core.Branch', on_delete=models.SET_NULL, related_name='mortality_records', null=True, blank=True)
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='mortality_records')
    quantity = models.IntegerField()
    reason = models.CharField(max_length=50, choices=MORTALITY_REASONS, default='unknown')
    date = models.DateField()
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    flock_quantity_applied = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.flock} - {self.quantity} birds ({self.date})"

    def clean(self):
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({'quantity': 'Mortality quantity must be greater than zero.'})

        if not self.flock_id or self.quantity is None:
            return

        available_quantity = self.flock.quantity
        if self.pk:
            old_record = MortalityRecord.objects.filter(pk=self.pk).select_related('flock').first()
            if old_record and old_record.flock_quantity_applied and old_record.flock_id == self.flock_id:
                available_quantity += old_record.quantity

        if self.quantity > available_quantity:
            raise ValidationError({
                'quantity': f'Mortality quantity cannot exceed the selected flock quantity ({available_quantity}).'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            old_record = None
            if self.pk:
                old_record = MortalityRecord.objects.select_for_update().get(pk=self.pk)
                if old_record.flock_quantity_applied:
                    old_flock = Flock.objects.select_for_update().get(pk=old_record.flock_id)
                    old_flock.quantity += old_record.quantity
                    old_flock.save(update_fields=['quantity', 'updated_at'])

            flock = Flock.objects.select_for_update().get(pk=self.flock_id)
            if self.quantity > flock.quantity:
                raise ValidationError({
                    'quantity': f'Mortality quantity cannot exceed the selected flock quantity ({flock.quantity}).'
                })

            flock.quantity -= self.quantity
            flock.save(update_fields=['quantity', 'updated_at'])
            self.flock_quantity_applied = True
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.flock_quantity_applied:
                flock = Flock.objects.select_for_update().get(pk=self.flock_id)
                flock.quantity += self.quantity
                flock.save(update_fields=['quantity', 'updated_at'])
            return super().delete(*args, **kwargs)
    
    class Meta:
        ordering = ['branch__name', '-date', '-created_at']


class BreedInformation(models.Model):
    """Detailed breed information."""
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=50)
    egg_production_per_year = models.IntegerField(null=True, blank=True)
    growth_period_days = models.IntegerField(null=True, blank=True)
    average_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feed_consumption_daily_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lifespan_years = models.IntegerField(null=True, blank=True)
    characteristics = models.TextField(blank=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Breed Information"


class HealthRecord(models.Model):
    """Health and vaccination records."""
    HEALTH_STATUS = [
        ('healthy', 'Healthy'),
        ('sick', 'Sick'),
        ('treated', 'Treated'),
        ('recovered', 'Recovered'),
    ]
    
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='health_records')
    health_status = models.CharField(max_length=50, choices=HEALTH_STATUS, default='healthy')
    disease_name = models.CharField(max_length=100, blank=True)
    treatment = models.TextField(blank=True)
    medication = models.CharField(max_length=255, blank=True)
    vaccination_name = models.CharField(max_length=100, blank=True)
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.flock} - {self.health_status} ({self.date})"
    
    class Meta:
        ordering = ['-date']
