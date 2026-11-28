"""Branch-level Flock ID numbering and same-ID isolation across branches."""
import re
import threading
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest import mock, skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from core.models import AuditEvent, Branch, Farm
from flocks import numbering
from flocks.models import Flock, FlockIdSequence
from inventory.models import Inventory, InventoryDistribution
from production.models import MortalityRecord, ProductionRecord
from reports.models import Report
from revenue.models import Revenue


def make_farm(user, name='Farm'):
    return Farm.objects.create(owner=user, name=name, location='Town', established_date=timezone.localdate() - timedelta(days=400),
                               contact_email='owner@example.com', contact_phone='09123456789')


class FlockApiMixin:
    def create_flock(self, branch, breed='layers', quantity=100, client=None, **extra):
        payload = {'branch': branch.pk if branch else None, 'breed': breed, 'quantity': quantity,
                   'acquisition_source': 'own', **extra}
        if breed == 'broilers':
            payload.setdefault('placement_date', (timezone.localdate() - timedelta(days=40)).isoformat())
        return (client or self.client).post(reverse('flock-list'), payload, content_type='application/json')

    def new_flock(self, branch, **kwargs):
        response = self.create_flock(branch, **kwargs)
        self.assertEqual(response.status_code, 201, response.content)
        return Flock.objects.get(pk=response.json()['id'])


class FlockNumberingTests(FlockApiMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='numbering-owner')
        self.farm = make_farm(self.user)
        self.branch_a = Branch.objects.create(farm=self.farm, name='Branch A')
        self.branch_b = Branch.objects.create(farm=self.farm, name='Branch B')
        self.client.force_login(self.user)

    def ids(self, branch):
        return list(Flock.objects.filter(user=self.user, branch=branch).order_by('pk').values_list('flock_id', flat=True))

    def test_each_branch_including_main_branch_has_its_own_sequence(self):
        for branch in (self.branch_a, self.branch_b, None, self.branch_a, self.branch_b, None):
            self.new_flock(branch)
        self.assertEqual(self.ids(self.branch_a), ['01', '02'])
        self.assertEqual(self.ids(self.branch_b), ['01', '02'])
        self.assertEqual(self.ids(None), ['01', '02'])
        self.assertEqual(Flock.objects.filter(user=self.user).values('pk').distinct().count(), 6)

    def test_client_supplied_flock_id_is_ignored(self):
        response = self.create_flock(self.branch_a, flock_id='99')
        self.assertEqual(response.json()['flock_id'], '01')

    def test_broilers_and_layers_start_at_01_in_each_branch(self):
        for branch in (self.branch_a, self.branch_b, None):
            with self.subTest(branch=branch):
                for number in ('01', '02'):
                    layers = self.new_flock(branch, breed='layers')
                    broilers = self.new_flock(branch, breed='broilers')
                    self.assertEqual((layers.flock_id, broilers.flock_id), (number, number))
                    self.assertNotEqual(layers.pk, broilers.pk)
                    self.assertIn('Layers', layers.display_label)
                    self.assertIn('Broilers', broilers.display_label)

    def test_numbering_continues_past_99_without_a_cap(self):
        Flock.objects.create(user=self.user, branch=self.branch_a, flock_id='99', breed='layers', quantity=10)
        self.assertEqual(self.new_flock(self.branch_a).flock_id, '100')
        self.assertEqual(self.new_flock(self.branch_a).flock_id, '101')
        self.assertEqual(self.new_flock(self.branch_b).flock_id, '01')

    def test_deleted_and_archived_ids_are_not_reused(self):
        first, second, third = (self.new_flock(self.branch_a) for _ in range(3))
        self.assertEqual(self.client.delete(reverse('flock-detail', args=[third.pk])).status_code, 204)
        archived = self.client.patch(reverse('flock-detail', args=[second.pk]), {'status': 'retired'}, content_type='application/json')
        self.assertEqual(archived.status_code, 200, archived.content)
        self.assertEqual(self.new_flock(self.branch_a).flock_id, '04')
        Flock.objects.filter(branch=self.branch_a).delete()
        self.assertEqual(self.new_flock(self.branch_a).flock_id, '05')

    def test_legacy_ids_are_kept_and_numbering_follows_numeric_history(self):
        legacy = Flock.objects.create(user=self.user, branch=self.branch_a, flock_id='LAYERS-A', breed='layers', quantity=10)
        self.assertEqual(self.new_flock(self.branch_a).flock_id, '01')
        unpadded = Flock.objects.create(user=self.user, branch=self.branch_b, flock_id='7', breed='layers', quantity=10)
        self.assertEqual(self.new_flock(self.branch_b).flock_id, '08')
        legacy.refresh_from_db(); unpadded.refresh_from_db()
        self.assertEqual((legacy.flock_id, unpadded.flock_id), ('LAYERS-A', '7'))

    def test_bulk_inserted_rows_without_counter_are_still_skipped(self):
        Flock.objects.bulk_create([Flock(user=self.user, branch=self.branch_a, flock_id='05', breed='layers', quantity=1)])
        self.assertEqual(self.new_flock(self.branch_a).flock_id, '06')

    def test_moved_flock_takes_next_id_in_new_branch_and_keeps_its_records(self):
        self.new_flock(self.branch_a)
        moving = self.new_flock(self.branch_a)
        self.new_flock(self.branch_b)
        record = ProductionRecord.objects.create(user=self.user, branch=self.branch_a, flock=moving, product_type='eggs',
                                                 egg_size='small', quantity=5, unit='eggs', date=timezone.localdate())
        response = self.client.patch(reverse('flock-detail', args=[moving.pk]), {'branch': self.branch_b.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['id'], response.json()['flock_id']), (moving.pk, '02'))
        record.refresh_from_db()
        self.assertEqual(record.flock_id, moving.pk)
        # Branch A already issued 02, so it is not reissued after the move.
        self.assertEqual(self.new_flock(self.branch_a).flock_id, '03')

    def test_accounts_number_independently_and_cannot_use_another_farms_branch(self):
        other = get_user_model().objects.create_user(username='numbering-neighbor')
        other_branch = Branch.objects.create(farm=make_farm(other, 'Neighbor farm'), name='Branch A')
        self.new_flock(self.branch_a)
        other_client = Client(); other_client.force_login(other)
        self.assertEqual(self.new_flock(other_branch, client=other_client).flock_id, '01')
        foreign = self.create_flock(self.branch_a, client=other_client)
        self.assertEqual(foreign.status_code, 400)
        self.assertEqual(Flock.objects.filter(branch=self.branch_a).count(), 1)

    def test_conflicting_concurrent_number_is_retried_with_the_next_id(self):
        self.new_flock(self.branch_a)
        real = numbering.next_flock_id
        calls = []

        def stale_then_real(user_id, branch_id, breed):
            calls.append(branch_id)
            return '01' if len(calls) == 1 else real(user_id, branch_id, breed)

        with mock.patch('flocks.views.next_flock_id', side_effect=stale_then_real):
            flock = self.new_flock(self.branch_a)
        self.assertEqual((flock.flock_id, len(calls)), ('02', 2))
        self.assertEqual(self.ids(self.branch_a), ['01', '02'])

    def test_branch_whose_flocks_were_deleted_can_still_be_deleted(self):
        flock = self.new_flock(self.branch_b)
        self.client.delete(reverse('flock-detail', args=[flock.pk]))
        response = self.client.post(reverse('farm_branches'), {'action': 'delete', 'branch_id': self.branch_b.pk}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Branch.objects.filter(pk=self.branch_b.pk).exists())
        self.assertFalse(FlockIdSequence.objects.filter(branch_id=self.branch_b.pk).exists())

    def test_account_with_matching_ids_in_two_branches_can_be_deleted(self):
        self.new_flock(self.branch_a); self.new_flock(self.branch_b)
        self.user.delete()
        self.assertFalse(Flock.objects.exists())
        self.assertFalse(FlockIdSequence.objects.exists())


class SameFlockIdAcrossBranchesTests(FlockApiMixin, TestCase):
    """Branch A and Branch B both have flock 01 (and 02); every action must hit only the intended flock."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='same-id-owner')
        farm = make_farm(self.user)
        self.branch_a = Branch.objects.create(farm=farm, name='Branch A')
        self.branch_b = Branch.objects.create(farm=farm, name='Branch B')
        self.client.force_login(self.user)
        self.layers_a = self.new_flock(self.branch_a, breed='layers', quantity=100)
        self.layers_b = self.new_flock(self.branch_b, breed='layers', quantity=100)
        self.broilers_a = self.new_flock(self.branch_a, breed='broilers', quantity=50)
        self.broilers_b = self.new_flock(self.branch_b, breed='broilers', quantity=50)
        self.today = timezone.localdate()
        assert (self.layers_a.flock_id, self.layers_b.flock_id, self.broilers_a.flock_id, self.broilers_b.flock_id) == ('01', '01', '01', '01')

    def quantities(self):
        return {flock.pk: Flock.objects.get(pk=flock.pk).quantity for flock in (self.layers_a, self.layers_b, self.broilers_a, self.broilers_b)}

    def eggs(self, flock, branch, quantity=60):
        return ProductionRecord.objects.create(user=self.user, branch=branch, flock=flock, product_type='eggs', egg_size='medium',
                                               quantity=quantity, unit='eggs', date=self.today)

    def test_production_record_goes_only_to_selected_branch_flock(self):
        before = self.quantities()
        response = self.client.post(reverse('production-list'), {'branch': self.branch_a.pk, 'flock': self.broilers_a.pk,
            'product_type': 'meat_ready', 'quantity': '5', 'unit': 'birds', 'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 201, response.content)
        record = ProductionRecord.objects.get(pk=response.json()['id'])
        self.assertEqual((record.flock_id, record.branch_id), (self.broilers_a.pk, self.branch_a.pk))
        self.assertEqual(self.quantities(), {**before, self.broilers_a.pk: 45})
        self.assertFalse(ProductionRecord.objects.filter(flock=self.broilers_b).exists())

    def test_production_form_page_saves_to_selected_branch_flock(self):
        response = self.client.post(reverse('production_record_create'), {'branch': self.branch_b.pk, 'flock': self.layers_b.pk,
            'product_type': 'eggs', 'egg_size': 'small', 'quantity': '30', 'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['form'].errors)
        self.assertEqual(list(ProductionRecord.objects.values_list('flock_id', 'branch_id')), [(self.layers_b.pk, self.branch_b.pk)])

    def test_production_with_other_branchs_same_id_flock_is_rejected(self):
        before = self.quantities()
        response = self.client.post(reverse('production-list'), {'branch': self.branch_a.pk, 'flock': self.broilers_b.pk,
            'product_type': 'meat_ready', 'quantity': '5', 'unit': 'birds', 'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 400)
        self.assertIn('flock', response.json())
        self.assertFalse(ProductionRecord.objects.exists())
        self.assertEqual(self.quantities(), before)

    def test_mortality_updates_only_selected_branch_flock(self):
        before = self.quantities()
        response = self.client.post(reverse('mortality_record_create'), {'branch': self.branch_b.pk, 'flock': self.layers_b.pk,
            'quantity': 4, 'reason': 'disease', 'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 302)
        api = self.client.post(reverse('mortality-list'), {'branch': self.branch_a.pk, 'flock': self.layers_a.pk,
            'quantity': 3, 'reason': 'disease', 'date': self.today.isoformat()})
        self.assertEqual(api.status_code, 201, api.content)
        self.assertEqual(self.quantities(), {**before, self.layers_b.pk: 96, self.layers_a.pk: 97})
        self.assertEqual(sorted(MortalityRecord.objects.values_list('flock_id', 'branch_id')),
                         sorted([(self.layers_b.pk, self.branch_b.pk), (self.layers_a.pk, self.branch_a.pk)]))
        mismatch = self.client.post(reverse('mortality-list'), {'branch': self.branch_a.pk, 'flock': self.layers_b.pk,
            'quantity': 1, 'reason': 'disease', 'date': self.today.isoformat()})
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(Flock.objects.get(pk=self.layers_b.pk).quantity, 96)

    def test_sales_reduce_only_the_selected_branch_stock(self):
        batch_a, batch_b = self.eggs(self.layers_a, self.branch_a), self.eggs(self.layers_b, self.branch_b)
        meat_a = ProductionRecord.objects.create(user=self.user, branch=self.branch_a, flock=self.broilers_a, product_type='meat_ready',
                                                 quantity=10, unit='birds', date=self.today)
        meat_b = ProductionRecord.objects.create(user=self.user, branch=self.branch_b, flock=self.broilers_b, product_type='meat_ready',
                                                 quantity=10, unit='birds', date=self.today)
        before = self.quantities()
        response = self.client.post(reverse('revenue-order'), {'buyer_name': 'Buyer', 'date': self.today.isoformat(), 'items': [
            {'production': batch_b.pk, 'quantity': '12', 'price_per_unit': '8'},
            {'production': meat_a.pk, 'quantity': '4', 'price_per_unit': '200'}]}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(sorted(Revenue.objects.values_list('production_id', 'branch_id', 'flock_id')),
                         sorted([(batch_b.pk, self.branch_b.pk, self.layers_b.pk), (meat_a.pk, self.branch_a.pk, self.broilers_a.pk)]))
        for batch, available in ((batch_a, 60), (batch_b, 48), (meat_a, 6), (meat_b, 10)):
            self.assertEqual(ProductionRecord.objects.get(pk=batch.pk).available_quantity, available)
        self.assertEqual(self.quantities(), before)  # Live birds were already moved when the meat batch was recorded.

    def test_single_sale_with_a_mismatched_branch_is_rejected(self):
        batch_a = self.eggs(self.layers_a, self.branch_a)
        response = self.client.post(reverse('revenue-list'), {'production': batch_a.pk, 'branch': self.branch_b.pk, 'buyer_name': 'Buyer',
            'quantity': '5', 'price_per_unit': '8', 'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Revenue.objects.exists())
        matched = self.client.post(reverse('revenue-list'), {'production': batch_a.pk, 'branch': self.branch_a.pk, 'buyer_name': 'Buyer',
            'quantity': '5', 'price_per_unit': '8', 'date': self.today.isoformat()})
        self.assertEqual(matched.status_code, 201, matched.content)
        self.assertEqual(Revenue.objects.get().flock_id, self.layers_a.pk)

    def test_branch_filtered_dropdowns_carry_primary_key_and_branch(self):
        page = self.client.get(reverse('production_record_create')).content.decode()
        flock_select = re.search(r'<select name="flock".*?</select>', page, re.S).group(0)
        for flock in (self.layers_a, self.layers_b):
            tag = re.search(rf'<option value="{flock.pk}"[^>]*>', flock_select).group(0)
            self.assertIn(f'data-branch-id="{flock.branch_id}"', tag)
        stock = {self.eggs(self.layers_a, self.branch_a).pk: self.branch_a.pk, self.eggs(self.layers_b, self.branch_b).pk: self.branch_b.pk}
        items = self.client.get(reverse('revenue-available-production')).json()
        self.assertEqual({item['id']: item['branch'] for item in items if item['id'] in stock}, stock)

    def test_feed_report_and_excel_export_resolve_each_branch_flock(self):
        self.eggs(self.layers_a, self.branch_a, 60); self.eggs(self.layers_b, self.branch_b, 25)
        MortalityRecord.objects.create(user=self.user, branch=self.branch_b, flock=self.layers_b, quantity=2, reason='disease', date=self.today)
        feed = Inventory.objects.create(user=self.user, item_type='feed', name='Feed', quantity=Decimal('100'), unit='kg',
                                        cost_per_unit=Decimal('10'), date_added=self.today)
        for branch, flock in ((self.branch_a, self.layers_a), (self.branch_b, self.layers_b)):
            InventoryDistribution.objects.create(user=self.user, inventory=feed, branch=branch, flock=flock, quantity=Decimal('5'), date=self.today)
        report = self.client.get(reverse('report-feed-usage'), {'start': self.today, 'end': self.today, 'branch': self.branch_a.pk})
        self.assertEqual(report.status_code, 200, report.content)
        self.assertEqual([(row['branch'], row['flock'], row['flock_id'], row['eggs_produced']) for row in report.data['results']],
                         [('Branch A', '01', self.layers_a.pk, '60.00')])

        saved = Report.objects.create(user=self.user, report_type='daily', title='Daily', start_date=self.today, end_date=self.today)
        download = self.client.get(f'/api/reports/{saved.id}/download/')
        self.assertEqual(download.status_code, 200)
        workbook = load_workbook(BytesIO(download.content))

        def rows(sheet, *columns):
            header = [cell.value for cell in workbook[sheet][1]]
            index = [header.index(column) for column in columns]
            return [tuple(row[i] for i in index) for row in workbook[sheet].iter_rows(min_row=2, values_only=True) if row[index[0]] in ('Branch A', 'Branch B')]

        self.assertEqual(sorted(rows('Production', 'Branch', 'Flock', 'Quantity')), [('Branch A', '01', 60), ('Branch B', '01', 25)])
        self.assertEqual(rows('Mortality', 'Branch', 'Flock', 'Quantity'), [('Branch B', '01', 2)])
        self.assertEqual(sorted(rows('Flocks', 'Branch', 'Flock ID', 'Breed')), [
            ('Branch A', '01', 'Broilers'), ('Branch A', '01', 'Layers'),
            ('Branch B', '01', 'Broilers'), ('Branch B', '01', 'Layers'),
        ])

    def test_linked_records_still_open_and_show_branch_with_flock(self):
        batch = self.eggs(self.layers_b, self.branch_b)
        MortalityRecord.objects.create(user=self.user, branch=self.branch_a, flock=self.layers_a, quantity=1, reason='disease', date=self.today)
        sale = Revenue.objects.create(user=self.user, production=batch, buyer_name='Buyer', quantity=Decimal('5'),
                                      price_per_unit=Decimal('8'), date=self.today)
        self.assertEqual((sale.branch_id, sale.flock_id), (self.branch_b.pk, self.layers_b.pk))
        for name, args in (('production_records', []), ('mortality_records', []), ('sales_receipt', [sale.pk]),
                           ('activity_history', []), ('production_record_update', [batch.pk]), ('dashboard', [])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        self.assertContains(self.client.get(reverse('production_records')), 'Branch B')

    def test_notifications_name_the_branch_with_the_flock_id(self):
        from notifications.models import Notification
        self.client.post(reverse('mortality_record_create'), {'branch': self.branch_b.pk, 'flock': self.layers_b.pk,
            'quantity': 1, 'reason': 'disease', 'date': self.today.isoformat()})
        self.assertTrue(Notification.objects.filter(user=self.user, message__contains='flock 01 (Branch B)').exists())


class FlockSequenceMigrationTests(TransactionTestCase):
    """Existing flocks keep their IDs and keys; counters start from current and historical numbers."""
    previous = ('flocks', '0010_alter_flock_acquisition_source')

    def targets(self, executor, flocks_node):
        # Every other app stays at its latest migration; only flocks moves.
        return [node for node in executor.loader.graph.leaf_nodes() if node[0] != 'flocks'] + [flocks_node]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_migration_preserves_flocks_and_seeds_each_branch_counter(self):
        executor = MigrationExecutor(connection)
        before = self.targets(executor, self.previous)
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        owner = old.get_model(settings.AUTH_USER_MODEL).objects.create(username='migrated-owner')
        farm = old.get_model('core', 'Farm').objects.create(owner=owner, name='Farm', location='Town', established_date='2025-01-01',
                                                            contact_email='m@example.com', contact_phone='09123456789')
        OldBranch, OldFlock = old.get_model('core', 'Branch'), old.get_model('flocks', 'Flock')
        branch_a, branch_b = OldBranch.objects.create(farm=farm, name='Branch A'), OldBranch.objects.create(farm=farm, name='Branch B')
        sample_branch = OldBranch.objects.create(pk=24, farm=farm, name='Sample Layers Branch')
        sample_layer = OldFlock.objects.create(user=owner, branch=sample_branch, breed='layers', flock_id='01', quantity=48)
        sample_broiler = OldFlock.objects.create(
            pk=58, user=owner, branch=sample_branch, breed='broilers', flock_id='11', quantity=50,
            acquisition_source='purchased', purchase_date='2026-11-28', purchase_amount=2250,
        )
        OldFlock.objects.filter(pk=sample_broiler.pk).update(date_added='2026-11-28')
        purchase = old.get_model('expenses', 'Expense').objects.create(
            user=owner, branch=sample_branch, flock_purchase=sample_broiler, expense_type='flock_purchase',
            description='Flock purchase: 11', amount=2250, date='2026-11-28',
        )
        mortality = old.get_model('production', 'MortalityRecord').objects.create(
            user=owner, branch=sample_branch, flock=sample_broiler, quantity=1, reason='disease', date='2026-11-28',
        )
        flocks = {
            'a1': OldFlock.objects.create(user=owner, branch=branch_a, flock_id='01', breed='layers', quantity=20),
            'a3': OldFlock.objects.create(user=owner, branch=branch_a, flock_id='03', breed='layers', quantity=20),
            'b2': OldFlock.objects.create(user=owner, branch=branch_b, flock_id='02', breed='layers', quantity=20),
            'main': OldFlock.objects.create(user=owner, branch=None, flock_id='05', breed='layers', quantity=20),
            'legacy': OldFlock.objects.create(user=owner, branch=branch_b, flock_id='LAY-B', breed='layers', quantity=20),
        }
        AuditEvent = old.get_model('core', 'AuditEvent')
        AuditEvent.objects.create(owner=owner, object_type='flocks.Flock', object_id=999, action='deleted',
                                  before={'branch_id': str(branch_b.pk), 'breed': 'layers', 'flock_id': '07'}, after={})
        AuditEvent.objects.create(owner=owner, object_type='flocks.Flock', object_id=998, action='deleted',
                                  before={'branch_id': '424242', 'flock_id': '50'}, after={})  # Branch no longer exists.
        old.get_model('production', 'ProductionRecord').objects.create(user=owner, branch=branch_a, flock=flocks['a1'], product_type='eggs',
                                                                      egg_size='small', quantity=10, unit='eggs', date='2026-11-01')

        executor = MigrationExecutor(connection)
        after = self.targets(executor, ('flocks', '0011_flock_id_sequence'))
        executor.migrate(after)
        new = executor.loader.project_state(after).apps
        counters = {row.branch_id: row.last_number for row in new.get_model('flocks', 'FlockIdSequence').objects.filter(user_id=owner.pk)}
        self.assertEqual(counters, {branch_a.pk: 3, branch_b.pk: 7, sample_branch.pk: 11, None: 5})
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

        for key, row in flocks.items():
            self.assertEqual(Flock.objects.get(pk=row.pk).flock_id, row.flock_id, key)
        self.assertEqual(Flock.objects.get(pk=sample_layer.pk).flock_id, '01')
        self.assertEqual(Flock.objects.get(pk=sample_broiler.pk).flock_id, '01')
        self.assertEqual(MortalityRecord.objects.get(pk=mortality.pk).flock_id, sample_broiler.pk)
        from expenses.models import Expense
        self.assertEqual(
            Expense.objects.values_list('flock_purchase_id', 'description', 'amount').get(pk=purchase.pk),
            (sample_broiler.pk, 'Flock purchase: 01', Decimal('2250.00')),
        )
        self.assertEqual(FlockIdSequence.objects.get(branch_id=sample_branch.pk, breed='broilers').last_number, 1)
        record = ProductionRecord.objects.get()
        self.assertEqual((record.flock_id, record.flock.flock_id), (flocks['a1'].pk, '01'))
        client = Client(); client.force_login(get_user_model().objects.get(pk=owner.pk))
        page = client.get(reverse('production_records'))
        self.assertContains(page, 'Branch A')
        self.assertEqual(client.get(reverse('production_record_update', args=[record.pk])).status_code, 200)
        created = [client.post(reverse('flock-list'), {'branch': branch.pk if branch else None, 'breed': 'layers', 'quantity': 5,
                                                       'acquisition_source': 'own'}, content_type='application/json').json()['flock_id']
                   for branch in (branch_a, branch_b, None)]
        self.assertEqual(created, ['04', '08', '06'])


@skipUnless(connection.vendor == 'postgresql', 'Needs real row locks and concurrent connections (PostgreSQL).')
class ConcurrentFlockCreationTests(TransactionTestCase):
    def test_simultaneous_creates_in_one_branch_get_distinct_sequential_ids(self):
        user = get_user_model().objects.create_user(username='concurrent-owner')
        branch = Branch.objects.create(farm=make_farm(user), name='Branch A')
        start, results = threading.Barrier(8), []

        def create():
            try:
                client = Client(); client.force_login(user); start.wait()
                response = client.post(reverse('flock-list'), {'branch': branch.pk, 'breed': 'layers', 'quantity': 5,
                                                              'acquisition_source': 'own'}, content_type='application/json')
                results.append((response.status_code, response.json().get('flock_id')))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=create) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sorted(results), [(201, f'{n:02d}') for n in range(1, 9)])
