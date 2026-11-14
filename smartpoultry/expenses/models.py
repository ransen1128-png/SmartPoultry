from django.db import models
from django.conf import settings
from core.models import Branch
from django.core.exceptions import ValidationError


class Expense(models.Model):
    """Expense/cost tracking."""
    EXPENSE_TYPES = [
        ('return_eggs','Return Eggs'),
        ('return_item','Return Item'),
        ('flock_purchase','Flock Purchase'),
        ('feed', 'Feed'),
        ('medicine', 'Medicine'),
        ('equipment', 'Equipment'),
        ('labor', 'Labor'),
        ('utilities', 'Utilities'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expense_records', null=True, blank=True)
    branch = models.ForeignKey('core.Branch', on_delete=models.SET_NULL, related_name='expense_records', null=True, blank=True)
    expense_type = models.CharField(max_length=50, choices=EXPENSE_TYPES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()
    category = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    return_quantity = models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    return_unit = models.CharField(max_length=50,blank=True)
    return_item_name = models.CharField(max_length=255,blank=True)
    inventory_purchase = models.OneToOneField('inventory.Inventory', on_delete=models.CASCADE, null=True, blank=True, related_name='purchase_expense')
    inventory_distribution = models.OneToOneField('inventory.InventoryDistribution', on_delete=models.CASCADE, null=True, blank=True, related_name='expense')
    flock_purchase = models.OneToOneField('flocks.Flock',on_delete=models.PROTECT,null=True,blank=True,related_name='purchase_expense')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.expense_type not in ('return_eggs','return_item'):
            if self.return_quantity is not None or self.return_unit or self.return_item_name:
                raise ValidationError('Return details apply only to returned items or eggs.')
            return
        errors={}
        if self.return_quantity is None or self.return_quantity<=0:errors['return_quantity']='Enter a returned quantity greater than zero.'
        if not self.return_unit.strip():errors['return_unit']='Enter the quantity unit, such as pcs, sacks or bottles.'
        if not self.description.strip():errors['description']='Enter the return reason.'
        if self.amount is None or self.amount<0:errors['amount']='Return expense must not be negative.'
        if self.expense_type=='return_item' and not self.return_item_name.strip():errors['return_item_name']='Enter the returned item name.'
        if not self.branch_id:errors['branch']='Select the branch responsible for this return.'
        elif self.branch.status!='active':errors['branch']='Select an active branch.'
        if errors:raise ValidationError(errors)

    def save(self,*args,**kwargs):
        self.clean()
        if self.expense_type in ('return_eggs','return_item'):self.category='returns'
        return super().save(*args,**kwargs)

    def __str__(self):
        return f"{self.expense_type.upper()} - {self.amount} ({self.date})"

    class Meta:
        ordering = ['branch__name', '-date', '-created_at']
