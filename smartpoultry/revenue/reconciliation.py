"""Conservative review of legacy sales; never infer a missing source flock."""
from production.models import ProductionRecord


def matching_production(sale):
    product={'eggs':'eggs','meat':'meat_ready'}.get(sale.revenue_type)
    if not product:
        return []
    records=ProductionRecord.objects.filter(user_id=sale.user_id,product_type=product,date__lte=sale.date,
        flock__status='active').exclude(branch__status='inactive').exclude(flock__branch__status='inactive').select_related('flock','branch')
    if sale.flock_id:records=records.filter(flock_id=sale.flock_id)
    if sale.branch_id:records=records.filter(branch_id=sale.branch_id)
    return [record for record in records if record.unit.strip().casefold()==sale.unit.strip().casefold()
            and record.available_quantity>=sale.quantity]


def review_sale(sale):
    candidates=matching_production(sale)
    reasons=[]
    if not sale.flock_id:reasons.append('Source flock was not recorded; verify the original sale before linking.')
    if not candidates:reasons.append('No single available production batch matches product, unit, date and quantity.')
    elif len(candidates)>1:reasons.append('Several batches fit; select the actual source batch.')
    return {'id':sale.pk,'date':sale.date.isoformat(),'product':sale.get_revenue_type_display(),
        'quantity':str(sale.quantity),'unit':sale.unit,'amount':str(sale.total_amount),'reasons':reasons,
        'candidates':[{'id':p.pk,'label':f'{p.flock.flock_id} — {p.date} — {p.available_quantity} {p.unit} available'} for p in candidates]}
