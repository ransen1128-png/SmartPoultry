"""Owner-scoped financial expenses and physical feed deliveries are separate."""
from collections import defaultdict
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum,Count
from rest_framework import serializers
from core.models import Branch
from expenses.models import Expense
from inventory.models import InventoryDistribution
from production.models import ProductionRecord


class Filters(serializers.Serializer):
    start=serializers.DateField(required=False)
    end=serializers.DateField(required=False)
    branch=serializers.CharField(required=False,allow_blank=True)


def filters(request):
    form=Filters(data=request.query_params);form.is_valid(raise_exception=True)
    values=form.validated_data
    today=timezone.localdate()
    start=values.get('start',today.replace(day=1));end=values.get('end',today)
    if end<start: raise serializers.ValidationError('End date must be on or after start date.')
    branch=values.get('branch')
    if branch and branch!='unassigned':
        if not branch.isdigit() or not Branch.objects.filter(pk=branch,farm__owner=request.user).exists():
            raise serializers.ValidationError({'branch':'Select a branch from your farm.'})
        branch=int(branch)
    return start,end,branch


def scope_branch(query,branch):
    if branch=='unassigned': return query.filter(branch__isnull=True)
    return query.filter(branch_id=branch) if branch else query


def expense_report(request):
    start,end,branch=filters(request)
    rows=scope_branch(Expense.objects.filter(user=request.user,date__range=(start,end)),branch)
    summary=list(rows.order_by('branch__name','expense_type').values('branch_id','branch__name','expense_type').annotate(amount=Sum('amount'),records=Count('pk')))
    for row in summary:
        row['branch_name']=row.pop('branch__name') or 'Unassigned inventory / farm costs'
        row['amount']=str(row['amount'])
    return {'start':start,'end':end,'date_basis':'Original financial/purchase date','total':str(rows.aggregate(total=Sum('amount'))['total'] or Decimal('0')),
            'summary':summary},rows.select_related('branch','inventory_distribution').order_by('date','pk')


def feed_report(request):
    start,end,branch=filters(request)
    rows=scope_branch(InventoryDistribution.objects.filter(user=request.user,inventory__item_type='feed',
        date__range=(start,end),reversed_at__isnull=True).select_related('branch','flock','inventory'),branch)
    grouped={}
    for row in rows:
        key=(row.branch_id,row.flock_id)
        group=grouped.setdefault(key,{'branch_id':row.branch_id,'branch':row.branch.name,'flock_id':row.flock_id,
            'flock':row.flock.flock_id if row.flock_id else 'Branch stock — flock not recorded',
            'quantities':defaultdict(Decimal),'cost':Decimal('0'),'missing_cost_records':0})
        group['quantities'][row.unit_snapshot or row.inventory.unit]+=row.quantity
        if row.cost_snapshot is None: group['missing_cost_records']+=1
        else: group['cost']+=row.cost_snapshot
    results=[]
    for group in grouped.values():
        group['quantities']={key:str(value) for key,value in group['quantities'].items()}
        eggs=Decimal('0');unsupported=False
        production=ProductionRecord.objects.filter(user=request.user,flock_id=group['flock_id'],branch_id=group['branch_id'],product_type='eggs',date__range=(start,end)) if group['flock_id'] else []
        for row in production:
            if row.unit.strip().lower() not in ('eggs','egg','units','unit','pcs','pc','pieces','piece'):
                unsupported=True
            else: eggs+=row.quantity
        group['eggs_produced']=str(eggs) if not unsupported and group['flock_id'] else None
        group['distributed_feed_cost_per_egg']=str((group['cost']/eggs).quantize(Decimal('.0001'))) if eggs and not unsupported and not group['missing_cost_records'] else None
        group['cost']=str(group['cost'])
        results.append(group)
    return {'start':start,'end':end,'date_basis':'Distribution and production dates','results':results,
            'limitation':'Feed delivered is not confirmed feed consumed. Units are kept separate. Cost per egg requires a recorded flock, known cost and production recorded as individual eggs; trays are not converted automatically.'}
