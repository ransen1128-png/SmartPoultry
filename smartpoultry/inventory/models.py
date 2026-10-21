from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone


class FeedType(models.Model):
    """Types of feed available."""
    name = models.CharField(max_length=100, unique=True)
    unit = models.CharField(max_length=50, default='kg')
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name


class Inventory(models.Model):
    """Feed and supply inventory tracking."""
    ITEM_TYPES = [
        ('feed', 'Feed'),
        ('medicine', 'Medicine'),
        ('equipment', 'Equipment'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inventory_items', null=True, blank=True)
    item_type = models.CharField(max_length=50, choices=ITEM_TYPES)
    name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50)
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, editable=False)
    date_added = models.DateField(auto_now_add=True)
    last_updated = models.DateField(auto_now=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.total_value = self.quantity * self.cost_per_unit
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"

    class Meta:
        ordering = ['-last_updated']


class InventoryDistribution(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inventory_distributions')
    inventory = models.ForeignKey(Inventory, on_delete=models.PROTECT, related_name='distributions')
    branch = models.ForeignKey('core.Branch', on_delete=models.PROTECT, related_name='inventory_distributions')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Distribution records cannot be edited.')
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Distribution quantity must be greater than zero.'})

        with transaction.atomic():
            inventory = Inventory.objects.select_for_update().get(pk=self.inventory_id)
            if inventory.user_id != self.user_id:
                raise ValidationError({'inventory': 'Select an inventory item from your account.'})
            if self.branch.farm.owner_id != self.user_id:
                raise ValidationError({'branch': 'Select a branch from your farm.'})
            if self.quantity > inventory.quantity:
                raise ValidationError({
                    'quantity': f'Only {inventory.quantity} {inventory.unit} available.'
                })

            inventory.quantity -= self.quantity
            inventory.save(update_fields=['quantity', 'total_value', 'last_updated'])
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            inventory = Inventory.objects.select_for_update().get(pk=self.inventory_id)
            inventory.quantity += self.quantity
            inventory.save(update_fields=['quantity', 'total_value', 'last_updated'])
            return super().delete(*args, **kwargs)

    class Meta:
        ordering = ['-date', '-created_at']
