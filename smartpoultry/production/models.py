from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from flocks.models import Flock
from core.models import Branch
from decimal import Decimal


class ProductionRecord(models.Model):
    """Daily production records for flocks."""
    PRODUCT_TYPES = [
        ('eggs', 'Eggs'),
        ('meat_ready', 'Meat Ready'),
    ]
    EGG_SIZES = [('small','Small'),('medium','Medium'),('large','Large')]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='production_records', null=True, blank=True)
    branch = models.ForeignKey('core.Branch', on_delete=models.SET_NULL, related_name='production_records', null=True, blank=True)
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='production_records')
    product_type = models.CharField(max_length=50, choices=PRODUCT_TYPES)
    egg_size = models.CharField(max_length=10,choices=EGG_SIZES,blank=True,default='')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, default='units')
    date = models.DateField()
    notes = models.TextField(blank=True)
    birds_removed = models.PositiveIntegerField(default=0,editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def sold_quantity(self):
        return self.__dict__.get('_sold_quantity') if '_sold_quantity' in self.__dict__ else (self.revenue_sales.aggregate(total=models.Sum('quantity'))['total'] or 0)

    @property
    def available_quantity(self):
        return self.quantity - self.sold_quantity

    def clean(self):
        if self.egg_size and self.egg_size not in dict(self.EGG_SIZES):
            raise ValidationError({'egg_size':'Choose Small, Medium or Large.'})
        if self.product_type!='eggs' and self.egg_size:
            raise ValidationError({'egg_size':'Egg size applies only to egg production.'})
        if self.quantity is not None and self.quantity<=0:
            raise ValidationError({'quantity':'Production quantity must be greater than zero.'})
        desired=self.bird_count()
        previous=type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if self.product_type=='meat_ready' and self.flock_id and (previous is None or any(getattr(self,f)!=getattr(previous,f) for f in ('flock_id','product_type','date','quantity'))):
            self.flock.validate_broiler_ready(self.date)
        if desired and (previous is None or previous.birds_removed):
            available=self.flock.quantity+(previous.birds_removed if previous and previous.flock_id==self.flock_id else 0)
            if desired>available:raise ValidationError({'quantity':f'Only {available} live chicken are available in this flock.'})
        if self.pk and self.quantity is not None and self.quantity < self.sold_quantity:
            raise ValidationError({'quantity': 'Production quantity cannot be less than the quantity already sold.'})
        if self.pk and self.revenue_sales.exists():
            previous = type(self).objects.get(pk=self.pk)
            if any(getattr(self, field) != getattr(previous, field) for field in ('user_id','branch_id','flock_id','product_type','egg_size','unit','date')):
                raise ValidationError('Production details with recorded sales cannot be changed; create a new entry.')

    def bird_count(self):
        if self.product_type!='meat_ready' or not self.flock_id or self.flock.breed!='broilers':return 0
        if self.unit.strip().lower() not in ('units','unit','birds','bird','chicken','chickens','pcs','pc','pieces','piece','head'):return 0
        value=Decimal(str(self.quantity)) if self.quantity is not None else Decimal('0')
        if value<=0 or value!=value.to_integral_value():
            raise ValidationError({'quantity':'Enter a whole number of broiler chicken.'})
        return int(value)

    @property
    def can_apply_bird_transfer(self):
        try:desired=self.bird_count()
        except ValidationError:return False
        return not self.birds_removed and desired>0 and desired<=self.flock.quantity and self.flock.status=='active'

    def apply_bird_transfer(self,actor):
        """Owner explicitly confirms that a legacy batch remains in live count."""
        from django.utils import timezone
        with transaction.atomic():
            current=type(self).objects.select_for_update(of=('self',)).get(pk=self.pk)
            flock=Flock.objects.select_for_update(of=('self',)).get(pk=current.flock_id)
            if current.user_id!=actor.pk or flock.user_id!=actor.pk:
                raise ValidationError('Select production from your own account.')
            if current.birds_removed:return 0
            if flock.status!='active' or (flock.branch_id and flock.branch.status!='active'):
                raise ValidationError('Select an active flock and branch.')
            flock.validate_broiler_ready(current.date)
            desired=current.bird_count()
            if not desired or desired>flock.quantity:
                raise ValidationError('The whole-chicken count cannot be transferred from the current live quantity. Review the original record.')
            flock.quantity-=desired
            flock.save(update_fields=['quantity','updated_at'])
            current.notes+=f'\nLive-chicken transfer confirmed by account #{actor.pk} at {timezone.now().isoformat()}: {desired} chicken.'
            type(self).objects.filter(pk=current.pk).update(birds_removed=desired,notes=current.notes,updated_at=timezone.now())
            from flocks.lifecycle import refresh_broiler_status
            refresh_broiler_status(flock)
            return desired

    def save(self, *args, **kwargs):
        with transaction.atomic():
            previous=type(self).objects.select_for_update(of=('self',)).get(pk=self.pk) if self.pk else None
            self.clean()
            desired=self.bird_count()
            # Older records have no applied bird movement: ordinary edits do not
            # silently re-count a historical flock whose opening count is unknown.
            if previous and not previous.birds_removed:desired=0
            ids={self.flock_id}|({previous.flock_id} if previous else set())
            locked={row.pk:row for row in Flock.objects.select_for_update(of=('self',)).filter(pk__in=ids).order_by('pk')}
            if previous and previous.birds_removed:locked[previous.flock_id].quantity+=previous.birds_removed
            if desired>locked[self.flock_id].quantity:
                raise ValidationError({'quantity':f'Only {locked[self.flock_id].quantity} live chicken are available in this flock.'})
            locked[self.flock_id].quantity-=desired
            self.birds_removed=desired
            if kwargs.get('update_fields') is not None:kwargs['update_fields']=set(kwargs['update_fields'])|{'birds_removed'}
            super().save(*args, **kwargs)
            from flocks.lifecycle import refresh_broiler_status
            for row in locked.values():
                row.save(update_fields=['quantity','updated_at'])
                refresh_broiler_status(row)

    def delete(self,*args,**kwargs):
        with transaction.atomic():
            current=type(self).objects.select_for_update(of=('self',)).get(pk=self.pk)
            flock=Flock.objects.select_for_update(of=('self',)).get(pk=current.flock_id)
            result=super().delete(*args,**kwargs)
            if current.birds_removed:
                flock.quantity+=current.birds_removed
                flock.save(update_fields=['quantity','updated_at'])
            from flocks.lifecycle import refresh_broiler_status
            refresh_broiler_status(flock)
            return result
    
    def __str__(self):
        return f"{self.flock} - {self.product_type} ({self.date})"
    
    class Meta:
        ordering = ['branch__name', '-date', '-created_at']
        unique_together = ('flock', 'product_type', 'date', 'egg_size')


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
        return f"{self.flock} - {self.quantity} chicken ({self.date})"

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
