from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0009_branch'),
        ('inventory', '0002_inventory_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='InventoryDistribution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, max_digits=10)),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='inventory_distributions', to='core.branch')),
                ('inventory', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='distributions', to='inventory.inventory')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_distributions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date', '-created_at'],
            },
        ),
    ]