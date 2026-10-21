from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flocks', '0004_flock_branch'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='flock',
            name='unique_flock_id_per_user',
        ),
        migrations.AddConstraint(
            model_name='flock',
            constraint=models.UniqueConstraint(
                fields=('user', 'branch', 'flock_id'),
                condition=models.Q(branch__isnull=False),
                name='flock_branch_id_uniq',
            ),
        ),
        migrations.AddConstraint(
            model_name='flock',
            constraint=models.UniqueConstraint(
                fields=('user', 'flock_id'),
                condition=models.Q(branch__isnull=True),
                name='flock_unassigned_id_uniq',
            ),
        ),
    ]