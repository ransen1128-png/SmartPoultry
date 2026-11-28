from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import Branch
from decimal import Decimal,ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.db import IntegrityError

# Flocks without a Branch belong to the original farm, shown as the main branch.
MAIN_BRANCH_LABEL = 'Main Branch'


def numeric_flock_id(value):
    """Return the number for an all-digit Flock ID ("07" -> 7); legacy text IDs return None."""
    value = (value or '').strip()
    return int(value) if value.isascii() and value.isdigit() else None


class FlockIdSequence(models.Model):
    """Highest Flock ID used for one breed in one branch (NULL = main branch).

    It only ever increases, so numbers of deleted, archived or moved flocks are not reissued.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flock_id_sequences')
    branch = models.ForeignKey('core.Branch', on_delete=models.CASCADE, related_name='flock_id_sequences', null=True, blank=True)
    breed = models.CharField(max_length=50)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'branch', 'breed'], condition=models.Q(branch__isnull=False), name='flock_seq_branch_breed_uniq'),
            models.UniqueConstraint(fields=['user', 'breed'], condition=models.Q(branch__isnull=True), name='flock_seq_main_breed_uniq'),
        ]

    @classmethod
    def reserve(cls, user_id, branch_id, breed, flock_id):
        """Raise the breed's counter in this branch to at least this Flock ID."""
        number = numeric_flock_id(flock_id)
        if not number or not user_id:
            return
        rows = cls.objects.filter(user_id=user_id, branch_id=branch_id, breed=breed)
        if rows.filter(last_number__lt=number).update(last_number=number) or rows.exists():
            return
        try:
            with transaction.atomic():
                rows.create(user_id=user_id, branch_id=branch_id, breed=breed, last_number=number)
        except IntegrityError:  # Another transaction created the counter first.
            rows.filter(last_number__lt=number).update(last_number=number)


class Flock(models.Model):
    """Flock/batch of poultry."""
    BREED_CHOICES = [
        ('layers', 'Layers'),
        ('broilers', 'Broilers'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('sold', 'Sold'),
        ('deceased', 'Deceased'),
        ('retired', 'Retired'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flocks', null=True, blank=True)
    # RESTRICT, not SET_NULL: moving a branch's flocks to the main branch would collide with its Flock IDs.
    # Deleting the whole account still works because the flocks are deleted with their user.
    branch = models.ForeignKey('core.Branch', on_delete=models.RESTRICT, related_name='flocks', null=True, blank=True)
    flock_id = models.CharField(max_length=100)
    breed = models.CharField(max_length=50, choices=BREED_CHOICES)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    date_added = models.DateField(auto_now_add=True)
    expected_production_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    auto_sold = models.BooleanField(default=False,editable=False)
    acquisition_source = models.CharField(max_length=20,choices=[('unknown','Not recorded'),('own','Raised on my farm'),('purchased','Bought')],default='unknown')
    purchase_amount = models.DecimalField(max_digits=15,decimal_places=2,default=0)
    delivery_cost = models.DecimalField(max_digits=15,decimal_places=2,default=0)
    purchase_date = models.DateField(null=True,blank=True)
    supplier = models.CharField(max_length=255,blank=True)
    placement_date = models.DateField(null=True,blank=True,verbose_name='Delivery / hatch date')

    @property
    def ready_from(self):
        return self.placement_date+timedelta(days=25) if self.breed=='broilers' and self.placement_date else None

    @property
    def readiness_window_end(self):
        return self.placement_date+timedelta(days=60) if self.breed=='broilers' and self.placement_date else None

    def validate_broiler_ready(self,on_date):
        if self.breed!='broilers':return
        if not self.placement_date:
            raise ValidationError({'date':'Set this broiler flock’s delivery / hatch date in Flocks before harvesting or selling.'})
        if on_date is None:return
        if on_date<self.ready_from:
            raise ValidationError({'date':f'Broilers require at least 25 days after delivery / hatch. Earliest harvest or sale: {self.ready_from:%Y-%m-%d}; expected window: {self.ready_from:%Y-%m-%d} to {self.readiness_window_end:%Y-%m-%d}.'})
        if on_date>timezone.localdate():
            raise ValidationError({'date':'A broiler harvest or sale cannot be recorded in advance. Record it on the actual date.'})

    @property
    def purchase_total(self):
        return (Decimal(str(self.purchase_amount))+Decimal(str(self.delivery_cost))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) if self.acquisition_source=='purchased' else Decimal('0')

    def validate_acquisition(self):
        amount=Decimal(str(self.purchase_amount));delivery=Decimal(str(self.delivery_cost))
        if amount<0 or delivery<0:raise ValidationError({'purchase_amount':'Purchase and delivery costs cannot be negative.'})
        if self.acquisition_source=='purchased':
            if not self.purchase_date:raise ValidationError({'purchase_date':'Enter the purchase date.'})
            if not self.branch_id or not self.user_id or self.branch.farm.owner_id!=self.user_id:
                raise ValidationError({'branch':'Assign the purchase to a branch in your own farm.'})
            if self.purchase_total<=0:raise ValidationError({'purchase_amount':'Enter the total chicken purchase cost or delivery fee.'})
        elif amount or delivery:
            raise ValidationError({'purchase_amount':'Only bought flocks have purchase and delivery charges.'})

    def save(self,*args,**kwargs):
        self.validate_acquisition()
        with transaction.atomic():
            super().save(*args,**kwargs)
            FlockIdSequence.reserve(self.user_id, self.branch_id, self.breed, self.flock_id)
            from .purchase_expenses import sync_purchase_expense
            sync_purchase_expense(self)

    @property
    def branch_label(self):
        return self.branch.name if self.branch_id else MAIN_BRANCH_LABEL

    @property
    def display_label(self):
        return f'{self.flock_id} ({self.branch_label}) · {self.get_breed_display()}'

    @property
    def in_history(self):
        return self.quantity<=0 or self.status in ('sold','deceased','retired')

    @property
    def history_reason(self):
        return self.get_status_display() if self.status in ('sold','deceased','retired') else ('No live chicken remaining' if self.quantity<=0 else '')

    def __str__(self):
        return f"{self.flock_id} - {self.breed} ({self.quantity})"

    class Meta:
        ordering = ['branch__name', '-date_added', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'branch', 'breed', 'flock_id'],
                condition=models.Q(branch__isnull=False),
                name='flock_branch_breed_id_uniq',
            ),
            models.UniqueConstraint(
                fields=['user', 'breed', 'flock_id'],
                condition=models.Q(branch__isnull=True),
                name='flock_main_breed_id_uniq',
            ),
        ]
