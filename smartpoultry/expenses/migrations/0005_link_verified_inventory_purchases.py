from decimal import Decimal, ROUND_HALF_UP
from django.db import migrations
from django.db.models import Sum


def link_purchases(apps, schema_editor):
    Inventory=apps.get_model('inventory','Inventory')
    Expense=apps.get_model('expenses','Expense')
    Distribution=apps.get_model('inventory','InventoryDistribution')
    db=schema_editor.connection.alias
    for item in Inventory.objects.using(db).all().iterator():
        purchases=Expense.objects.using(db).filter(user_id=item.user_id,category='inventory',
            notes__startswith=f'Auto-created from inventory item #{item.pk}:',inventory_purchase__isnull=True)
        if purchases.count()!=1: continue
        purchase=purchases.get()
        distributed=Distribution.objects.using(db).filter(inventory_id=item.pk).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        expected=((item.quantity+distributed)*item.cost_per_unit).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        # Link only when the recorded purchase, current cost and complete stock ledger agree.
        if purchase.branch_id or purchase.expense_type!=item.item_type or purchase.amount!=expected: continue
        Expense.objects.using(db).filter(pk=purchase.pk).update(inventory_purchase_id=item.pk)
        Inventory.objects.using(db).filter(pk=item.pk).update(purchase_cost_per_unit=item.cost_per_unit)


class Migration(migrations.Migration):
    dependencies=[('expenses','0004_alter_expense_options_expense_inventory_distribution_and_more')]
    operations=[migrations.RunPython(link_purchases,migrations.RunPython.noop)]
