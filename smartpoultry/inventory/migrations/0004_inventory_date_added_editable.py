import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_inventorydistribution'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inventory',
            name='date_added',
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
    ]