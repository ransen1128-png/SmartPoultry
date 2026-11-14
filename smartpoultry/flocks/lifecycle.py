"""Called while holding the flock row lock; never deletes a flock or its records."""
from django.db.models import Sum,F,Value,DecimalField
from django.db.models.functions import Coalesce


def refresh_broiler_status(flock):
    if flock.breed!='broilers':return
    if flock.status not in ('active','sold') or (flock.status=='sold' and not flock.auto_sold):return
    records=flock.production_records.filter(product_type='meat_ready')
    unsold=records.annotate(sold=Coalesce(Sum('revenue_sales__quantity'),Value(0),output_field=DecimalField())).filter(quantity__gt=F('sold')).exists()
    completed=flock.quantity==0 and records.filter(birds_removed__gt=0).exists() and not unsold
    status='sold' if completed else 'active'
    if flock.status!=status or flock.auto_sold!=completed:
        flock.status=status;flock.auto_sold=completed
        flock.save(update_fields=['status','auto_sold','updated_at'])
