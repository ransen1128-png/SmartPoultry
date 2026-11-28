from datetime import date
from decimal import Decimal

from django.db import migrations, models
from django.db.models import F, Q


def split_sequences(apps, schema_editor):
    db = schema_editor.connection.alias
    flocks = apps.get_model('flocks', 'Flock').objects.using(db)
    counters = apps.get_model('flocks', 'FlockIdSequence').objects.using(db)
    branches = apps.get_model('core', 'Branch').objects.using(db)
    events = apps.get_model('core', 'AuditEvent').objects.using(db)
    expenses = apps.get_model('expenses', 'Expense').objects.using(db)
    branch_owners = dict(branches.values_list('pk', 'farm__owner_id'))

    # Correct only the specific flock reported in Sample Layers Branch (branch 24).
    correction = flocks.filter(
        pk=58, branch_id=24, branch__name='Sample Layers Branch', user_id=branch_owners.get(24),
        flock_id='11', breed='broilers', date_added=date(2026, 11, 28),
        acquisition_source='purchased',
    ).annotate(total_cost=F('purchase_amount') + F('delivery_cost')).filter(total_cost=Decimal('2250.00')).first()
    corrected_pk = None
    if correction and correction.user_id:
        siblings = flocks.filter(user_id=correction.user_id, branch_id=correction.branch_id, flock_id='01')
        if siblings.filter(breed='layers').exists() and not siblings.filter(breed='broilers').exists():
            flocks.filter(pk=correction.pk).update(flock_id='01')
            expenses.filter(flock_purchase_id=correction.pk, description='Flock purchase: 11').update(
                description='Flock purchase: 01',
            )
            corrected_pk = correction.pk
            events.create(
                owner_id=correction.user_id, actor_label='System', object_type='flocks.Flock',
                object_id=correction.pk, action='updated', before={'flock_id': '11'}, after={'flock_id': '01'},
                reason='Corrected the broiler ID after enabling separate flock numbering by breed.',
            )

    highest = {}

    def note(owner, branch, breed, raw_id):
        value = str(raw_id or '').strip()
        if not owner or not breed or not (value.isascii() and value.isdigit()):
            return
        key = owner, branch, breed
        highest[key] = max(highest.get(key, 0), int(value))

    for owner, branch, breed, flock_id in flocks.values_list('user_id', 'branch_id', 'breed', 'flock_id').iterator():
        note(owner, branch, breed, flock_id)

    snapshots = events.filter(object_type='flocks.Flock').values_list('owner_id', 'object_id', 'before', 'after')
    for owner, object_id, before, after in snapshots.iterator():
        for snapshot in (before, after):
            if not isinstance(snapshot, dict) or not {'branch_id', 'breed', 'flock_id'} <= snapshot.keys():
                continue
            raw_branch = snapshot['branch_id']
            if raw_branch in (None, '', 'None'):
                branch = None
            elif str(raw_branch).isdigit() and branch_owners.get(int(raw_branch)) == owner:
                branch = int(raw_branch)
            else:
                continue
            breed, value = snapshot['breed'], snapshot['flock_id']
            if object_id == corrected_pk and (branch, breed, value) == (24, 'broilers', '11'):
                continue
            note(owner, branch, breed, value)

    counters.filter(breed='').delete()
    counter_model = apps.get_model('flocks', 'FlockIdSequence')
    counters.bulk_create([
        counter_model(user_id=owner, branch_id=branch, breed=breed, last_number=highest[owner, branch, breed])
        for owner, branch, breed in highest
    ], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ('expenses', '0007_expense_return_item_name_expense_return_quantity_and_more'),
        ('flocks', '0011_flock_id_sequence'),
    ]

    operations = [
        migrations.RemoveConstraint('flockidsequence', 'flock_seq_branch_uniq'),
        migrations.RemoveConstraint('flockidsequence', 'flock_seq_main_uniq'),
        migrations.RemoveConstraint('flock', 'flock_branch_id_uniq'),
        migrations.RemoveConstraint('flock', 'flock_unassigned_id_uniq'),
        migrations.AddField('flockidsequence', 'breed', models.CharField(default='', max_length=50), preserve_default=False),
        migrations.AddConstraint('flockidsequence', models.UniqueConstraint(
            fields=('user', 'branch', 'breed'), condition=Q(branch__isnull=False), name='flock_seq_branch_breed_uniq',
        )),
        migrations.AddConstraint('flockidsequence', models.UniqueConstraint(
            fields=('user', 'breed'), condition=Q(branch__isnull=True), name='flock_seq_main_breed_uniq',
        )),
        migrations.AddConstraint('flock', models.UniqueConstraint(
            fields=('user', 'branch', 'breed', 'flock_id'), condition=Q(branch__isnull=False), name='flock_branch_breed_id_uniq',
        )),
        migrations.AddConstraint('flock', models.UniqueConstraint(
            fields=('user', 'breed', 'flock_id'), condition=Q(branch__isnull=True), name='flock_main_breed_id_uniq',
        )),
        migrations.RunPython(split_sequences, migrations.RunPython.noop),
    ]
