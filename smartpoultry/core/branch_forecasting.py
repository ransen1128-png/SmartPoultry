"""Forecast each branch from its own records; warehouse stock stays farm-wide."""
from collections import defaultdict
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from expenses.models import Expense
from flocks.models import Flock
from inventory.models import Inventory,InventoryDistribution
from production.models import ProductionRecord
from revenue.models import Revenue
from .random_forest_forecast import random_forest_forecast
from inventory.quantities import measurement_totals


def add_months(value,months):
    index=value.month-1+months
    return value.replace(year=value.year+index//12,month=index%12+1,day=1)


def forecast_context(user,branches,selected_branch=None):
    today=timezone.localdate();month=today.replace(day=1)
    start=add_months(month,-23)
    history=[add_months(month,index) for index in range(-5,1)]
    future=[add_months(month,index) for index in (1,2,3)]
    def monthly(model,field,**extra):
        return list(model.objects.filter(user=user,date__gte=start,date__lte=today,**extra)
            .annotate(month=TruncMonth('date')).order_by().values('branch_id','month').annotate(total=Sum(field)))
    revenue=monthly(Revenue,'total_amount')
    expenses=monthly(Expense,'amount')
    production=monthly(ProductionRecord,'quantity',product_type='eggs')
    birds=list(Flock.objects.filter(user=user,status='active',quantity__gt=0).exclude(branch__status='inactive')
        .order_by().values('branch_id').annotate(total=Sum('quantity')))
    stock=measurement_totals(Inventory.objects.filter(user=user,item_type='feed'))
    deliveries=list(InventoryDistribution.objects.filter(user=user,inventory__item_type='feed',reversed_at__isnull=True,
        date__gte=history[0],date__lte=today).order_by('unit_snapshot').values('branch_id','unit_snapshot','package_size_snapshot','content_unit_snapshot').annotate(quantity=Sum('quantity')))

    def project(branch_id=None):
        def series(rows):
            totals=defaultdict(float)
            for row in rows:
                if branch_id is None or row['branch_id']==branch_id:
                    key=row['month'].date() if hasattr(row['month'],'date') else row['month']
                    totals[key]+=float(row['total'])
            return totals
        income=series(revenue);cost=series(expenses);eggs=series(production)
        income_history=[income[value] for value in history if value in income]
        cost_history=[cost[value] for value in history if value in cost]
        egg_history=[eggs[value] for value in history if value in eggs]
        reports={name:random_forest_forecast(f'{user.pk}:{branch_id}:{name}',values,month,future)
                 for name,values in [('revenue',income),('expenses',cost),('production',eggs)]}
        projected_revenue=reports['revenue']['forecasts'];projected_cost=reports['expenses']['forecasts']
        active_birds=sum(row['total'] for row in birds if branch_id is None or row['branch_id']==branch_id)
        feed_deliveries=defaultdict(float)
        for row in deliveries:
            if branch_id is None or row['branch_id']==branch_id:
                unit=row['content_unit_snapshot'] if row['package_size_snapshot'] is not None else row['unit_snapshot']
                quantity=row['quantity']*row['package_size_snapshot'] if row['package_size_snapshot'] is not None else row['quantity']
                feed_deliveries[unit]+=float(quantity)
        return {'revenue_forecast':projected_revenue[0],
            'expected_profit':round(projected_revenue[0]-projected_cost[0],2) if projected_revenue[0] is not None and projected_cost[0] is not None else None,
            'production_forecast':reports['production']['forecasts'][0],
            'model_reports':reports,
            'feed_demand':round(float(active_birds)*0.12*30,2),
            'feed_deliveries':[{'unit':unit,'quantity':quantity} for unit,quantity in sorted(feed_deliveries.items())],
            'encoded_months':len(set(income)|set(cost)|set(eggs)),
            'has_encoded_data':bool(income_history or cost_history or egg_history or active_birds),
            'chart_data':{'labels':[value.strftime('%b %Y') for value in history+future],
                'actualRevenue':[income.get(value) for value in history]+[None]*3,
                'forecastRevenue':[None]*6+projected_revenue}}

    selected=project(selected_branch.pk if selected_branch else None)
    comparisons=[{'branch':branch,**project(branch.pk)} for branch in branches]
    return {**selected,'branches':branches,'selected_branch':selected_branch,'branch_forecasts':comparisons,
        'feed_stock':sum(row['quantity'] for row in stock),'feed_stock_by_unit':stock}
