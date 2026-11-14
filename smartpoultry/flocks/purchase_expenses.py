"""A single fixed purchase expense; live stock movements never change its cost."""
from expenses.models import Expense


def sync_purchase_expense(flock):
    existing=Expense.objects.filter(flock_purchase=flock).order_by('pk').first()
    if flock.acquisition_source!='purchased' and existing is None:return
    if flock.acquisition_source=='purchased':
        values={'user_id':flock.user_id,'branch_id':flock.branch_id,'expense_type':'flock_purchase',
            'description':f'Flock purchase: {flock.flock_id}'[:255],'amount':flock.purchase_total,
            'date':flock.purchase_date,'category':'flock_purchase',
            'notes':f'Flock #{flock.pk}; chicken cost {flock.purchase_amount}; delivery cost {flock.delivery_cost}; supplier: {flock.supplier or "Not recorded"}.'}
    else:
        values={'amount':0,'notes':f'Flock #{flock.pk} corrected to {flock.get_acquisition_source_display()}; no purchase expense.'}
    if existing is None:
        Expense.objects.create(flock_purchase=flock,**values)
    else:
        changed=[name for name,value in values.items() if getattr(existing,name)!=value]
        if changed:
            for name in changed:setattr(existing,name,values[name])
            existing.save(update_fields=[*changed,'updated_at'])
