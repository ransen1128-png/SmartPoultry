from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0010_rooster_image_assessment')]

    operations = [
        migrations.AddField(
            model_name='roosterageestimate', name='analysis',
            field=models.JSONField(default=dict, blank=True),
        ),
    ]
