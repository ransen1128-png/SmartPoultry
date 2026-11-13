from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP


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
    purchase_cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, null=True, editable=False)
    date_added = models.DateField(default=timezone.localdate)
    last_updated = models.DateField(auto_now=True)
    notes = models.TextField(blank=True)
    minimum_stock = models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    low_stock_alerted = models.BooleanField(default=False,editable=False)

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.purchase_cost_per_unit = self.cost_per_unit
        self.total_value = (Decimal(str(self.quantity)) * Decimal(str(self.cost_per_unit))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)
        from .stock_alerts import refresh_stock_alert
        refresh_stock_alert(self)

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
    flock = models.ForeignKey('flocks.Flock',on_delete=models.PROTECT,null=True,blank=True,related_name='inventory_distributions')
    unit_snapshot = models.CharField(max_length=50,blank=True,editable=False)
    cost_snapshot = models.DecimalField(max_digits=15,decimal_places=2,null=True,editable=False)
    reversed_at = models.DateTimeField(null=True,editable=False)
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='reversed_distributions',editable=False)
    reversal_reason = models.CharField(max_length=500,blank=True,editable=False)

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
            if self.branch.status != 'active':
                raise ValidationError({'branch': 'Select an active branch.'})
            if self.flock_id and (self.flock.user_id!=self.user_id or self.flock.branch_id!=self.branch_id or self.flock.status!='active'):
                raise ValidationError({'flock':'Select an active flock from the receiving branch and your account.'})
            if self.quantity > inventory.quantity:
                raise ValidationError({
                    'quantity': f'Only {inventory.quantity} {inventory.unit} available.'
                })

            inventory.quantity -= self.quantity
            inventory.save(update_fields=['quantity', 'total_value', 'last_updated'])
            self.unit_snapshot=inventory.unit
            super().save(*args, **kwargs)
            from .expense_allocation import allocate_distribution
            allocate_distribution(self, inventory)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            inventory = Inventory.objects.select_for_update().get(pk=self.inventory_id)
            if self.reversed_at:
                return super().delete(*args,**kwargs)
            from .expense_allocation import reverse_allocation
            reverse_allocation(self, inventory)
            inventory.quantity += self.quantity
            inventory.save(update_fields=['quantity', 'total_value', 'last_updated'])
            return super().delete(*args, **kwargs)

    def reverse(self,actor,reason):
        if actor.pk!=self.user_id:
            raise ValidationError('This distribution belongs to another account.')
        if not reason.strip() or len(reason)>500:
            raise ValidationError({'reason':'Enter a reversal reason of 1-500 characters.'})
        with transaction.atomic():
            inventory=Inventory.objects.select_for_update().get(pk=self.inventory_id)
            current=type(self).objects.select_for_update().get(pk=self.pk)
            if current.reversed_at:
                return current
            current.reversed_by=actor
            current.reversal_reason=reason.strip()
            from .expense_allocation import reverse_allocation
            reverse_allocation(current,inventory,preserve=True)
            inventory.quantity+=current.quantity
            inventory.save(update_fields=['quantity','total_value','last_updated'])
            current.reversed_at=timezone.now()
            type(self).objects.filter(pk=current.pk).update(reversed_at=current.reversed_at,reversed_by=actor,reversal_reason=current.reversal_reason)
            return current

    class Meta:
        ordering = ['-date', '-created_at']
