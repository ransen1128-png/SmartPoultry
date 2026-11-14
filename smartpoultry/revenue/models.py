from django.db import models
from django.conf import settings
from flocks.models import Flock
from core.models import Branch
from django.core.exceptions import ValidationError
from django.db import transaction
from uuid import uuid4


class Revenue(models.Model):
    """Revenue/income tracking."""
    REVENUE_TYPES = [
        ('eggs', 'Eggs'),
        ('meat', 'Meat'),
        ('birds', 'Chicken'),
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
    buyer_name = models.CharField(max_length=255,blank=True)
    buyer_contact = models.CharField(max_length=255,blank=True)
    buyer_address = models.CharField(max_length=500,blank=True)
    order_number = models.CharField(max_length=100,blank=True)
    transaction_number = models.CharField(max_length=40,unique=True,null=True,blank=True,editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self._state.adding:
            if not self.order_number.strip():
                self.order_number='ORD-'+uuid4().hex.upper()
            self.transaction_number='TXN-'+uuid4().hex.upper()
        with transaction.atomic():
            previous=type(self).objects.select_for_update(of=('self',)).get(pk=self.pk) if self.pk else None
            if previous and previous.production_id and previous.production_id!=self.production_id:
                raise ValidationError({'production':'A recorded sale cannot be moved to another production batch. Delete the incorrect sale and record its replacement.'})
            flock=None
            if self.production_id:
                from production.models import ProductionRecord
                # All sales from a batch serialize on the same production row.
                production = ProductionRecord.objects.select_for_update(of=('self',)).get(pk=self.production_id)
                flock=Flock.objects.select_for_update(of=('self',)).get(pk=production.flock_id)
                if production.user_id != self.user_id:
                    raise ValidationError({'production': 'Select production from your account.'})
                if production.product_type!='eggs':
                    flock.validate_broiler_ready(self.date)
                editing_auto_sold=previous is not None and flock.status=='sold' and flock.auto_sold
                if (flock.status != 'active' and not editing_auto_sold) or (production.branch_id and production.branch.status != 'active'):
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
            if flock:
                from flocks.lifecycle import refresh_broiler_status
                refresh_broiler_status(flock)

    def delete(self,*args,**kwargs):
        with transaction.atomic():
            current=type(self).objects.select_for_update(of=('self',)).get(pk=self.pk)
            flock=None
            if current.production_id:
                from production.models import ProductionRecord
                production=ProductionRecord.objects.select_for_update(of=('self',)).get(pk=current.production_id)
                flock=Flock.objects.select_for_update(of=('self',)).get(pk=production.flock_id)
            result=super().delete(*args,**kwargs)
            if flock:
                from flocks.lifecycle import refresh_broiler_status
                refresh_broiler_status(flock)
            return result

    def __str__(self):
        return f"{self.revenue_type.upper()} - {self.total_amount} ({self.date})"

    class Meta:
        ordering = ['branch__name', '-date', '-created_at']
