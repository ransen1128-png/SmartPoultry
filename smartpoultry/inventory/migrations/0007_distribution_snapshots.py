from django.db import migrations


def snapshots(apps,schema_editor):
    Distribution=apps.get_model('inventory','InventoryDistribution')
    Expense=apps.get_model('expenses','Expense')
    db=schema_editor.connection.alias
    for row in Distribution.objects.using(db).select_related('inventory').all().iterator():
        expense=Expense.objects.using(db).filter(inventory_distribution_id=row.pk).first()
        Distribution.objects.using(db).filter(pk=row.pk).update(unit_snapshot=row.inventory.unit,cost_snapshot=expense.amount if expense else None)


class Migration(migrations.Migration):
    dependencies=[('inventory','0006_inventory_low_stock_alerted_inventory_minimum_stock_and_more'),('expenses','0005_link_verified_inventory_purchases')]
    operations=[migrations.RunPython(snapshots,migrations.RunPython.noop)]
