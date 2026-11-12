from datetime import date
from decimal import Decimal
from io import BytesIO
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from analytics.models import Prediction
from core.models import RoosterAgeEstimate, TransactionRecord, Farm, Branch
from expenses.models import Expense
from flocks.models import Flock
from inventory.models import Inventory, InventoryDistribution
from PIL import Image
from production.models import ProductionRecord, MortalityRecord
from core.forms import ProductionRecordForm
from reports.models import Report
from revenue.models import Revenue


class RegistrationTests(TestCase):
    def test_new_account_requires_login_before_dashboard(self):
        response = self.client.post(reverse('register'), {
            'username': 'new-farm-owner',
            'email': 'new-owner@example.com',
            'password': 'RegistrationTest123!',
            'password2': 'RegistrationTest123!',
        }, follow=True)
        self.assertEqual(response.redirect_chain, [(reverse('login'), 302)])
        self.assertContains(response, 'Account created successfully. Please log in.')
        self.assertNotIn('_auth_user_id', self.client.session)
        account = get_user_model().objects.get(username='new-farm-owner')
        self.assertTrue(account.is_active)
        self.assertTrue(account.check_password('RegistrationTest123!'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)
        login_response = self.client.post(reverse('login'), {
            'email': 'new-owner@example.com', 'password': 'RegistrationTest123!',
        })
        self.assertRedirects(login_response, reverse('dashboard'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), account.pk)


class BranchTrackingTests(TestCase):
    def test_records_reference_the_branch_they_came_from(self):
        user = get_user_model().objects.create_user(username='branch-owner', password='password123')
        farm = Farm.objects.create(
            owner=user,
            name='Branch Farm',
            location='Main City',
            established_date=date(2024, 1, 1),
            contact_email='owner@example.com',
            contact_phone='09123456789',
        )
        branch = Branch.objects.create(
            farm=farm,
            name='North Branch',
            location='North District',
            address='North Street',
            contact_number='09111111111',
            description='North branch',
        )
        flock = Flock.objects.create(
            user=user,
            branch=branch,
            flock_id='FLOCK-001',
            breed='layers',
            quantity=100,
            status='active',
        )

        production = ProductionRecord.objects.create(
            user=user,
            flock=flock,
            branch=branch,
            product_type='eggs',
            quantity=Decimal('30'),
            unit='eggs',
            date=date(2026, 7, 4),
        )
        mortality = MortalityRecord.objects.create(
            user=user,
            flock=flock,
            branch=branch,
            quantity=2,
            reason='disease',
            date=date(2026, 7, 5),
        )
        revenue = Revenue.objects.create(
            user=user,
            branch=branch,
            revenue_type='eggs',
            quantity=Decimal('12'),
            unit='tray',
            price_per_unit=Decimal('180'),
            date=date(2026, 7, 6),
        )
        expense = Expense.objects.create(
            user=user,
            branch=branch,
            expense_type='feed',
            description='Layer feed',
            amount=Decimal('1250.00'),
            date=date(2026, 7, 7),
            category='supplies',
        )

        self.assertEqual(flock.branch, branch)
        self.assertEqual(production.branch, branch)
        self.assertEqual(mortality.branch, branch)
        self.assertEqual(revenue.branch, branch)
        self.assertEqual(expense.branch, branch)

    def test_dashboard_filters_metrics_and_trends_by_branch_and_month(self):
        user = get_user_model().objects.create_user(username='dashboard-owner', password='password123')
        farm = Farm.objects.create(
            owner=user,
            name='Dashboard Farm',
            location='Main City',
            established_date=date(2024, 1, 1),
            contact_email='dashboard@example.com',
            contact_phone='09123456789',
        )
        north = Branch.objects.create(farm=farm, name='North Branch')
        south = Branch.objects.create(farm=farm, name='South Branch')
        north_flock = Flock.objects.create(
            user=user, branch=north, flock_id='NORTH-001', breed='layers', quantity=40, status='active',
        )
        Flock.objects.create(
            user=user, branch=south, flock_id='SOUTH-001', breed='layers', quantity=60, status='active',
        )
        Revenue.objects.create(
            user=user, branch=north, revenue_type='eggs', quantity=10, unit='tray',
            price_per_unit=20, date=date(2026, 6, 10),
        )
        Revenue.objects.create(
            user=user, branch=south, revenue_type='eggs', quantity=30, unit='tray',
            price_per_unit=30, date=date(2026, 6, 10),
        )
        Expense.objects.create(
            user=user, branch=north, expense_type='feed', description='North feed',
            amount=25, date=date(2026, 6, 11),
        )
        Expense.objects.create(
            user=user, branch=south, expense_type='feed', description='South feed',
            amount=100, date=date(2026, 6, 11),
        )
        ProductionRecord.objects.create(
            user=user, branch=north, flock=north_flock, product_type='eggs',
            quantity=11, unit='eggs', date=date(2026, 6, 12),
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'), {'branch': north.pk, 'month': 6, 'year': 2026})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_branch'], north)
        self.assertEqual(response.context['metrics']['revenue'], Decimal('200'))
        self.assertEqual(response.context['metrics']['expenses'], Decimal('25'))
        self.assertEqual(response.context['metrics']['feed_cost'], Decimal('25'))
        self.assertEqual(response.context['metrics']['total_birds'], 40)
        self.assertEqual(response.context['metrics']['production_total'], Decimal('11'))
        self.assertEqual(response.context['chart_data']['labels'][-1], 'Jun')
        self.assertEqual(response.context['chart_data']['revenue'][-1], 200.0)
        self.assertEqual(len(response.context['branch_summaries']), 1)
        self.assertEqual(response.context['branch_summaries'][0]['branch'], north)
        self.assertContains(response, 'Overview of North Branch performance')

        south_response = self.client.get(reverse('dashboard'), {'branch': south.pk, 'month': 6, 'year': 2026})
        self.assertEqual(south_response.context['metrics']['total_birds'], 60)
        self.assertEqual(south_response.context['metrics']['active_flocks'], 1)
        self.assertEqual(south_response.context['chart_data']['revenue'][-1], 900.0)
        self.assertEqual([row['branch'] for row in south_response.context['branch_summaries']], [south])

        all_response = self.client.get(reverse('dashboard'), {'branch': '', 'month': 6, 'year': 2026})
        self.assertIsNone(all_response.context['selected_branch'])
        self.assertEqual(all_response.context['metrics']['total_birds'], 100)
        self.assertEqual(all_response.context['metrics']['active_flocks'], 2)
        self.assertEqual(all_response.context['metrics']['revenue'], Decimal('1100'))
        self.assertEqual(all_response.context['metrics']['expenses'], Decimal('125'))
        self.assertEqual(all_response.context['chart_data']['revenue'][-1], 1100.0)
        self.assertEqual({row['branch'] for row in all_response.context['branch_summaries']}, {north, south})


class DashboardInventoryFeedCostTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='feed-dashboard-owner', password='password123')
        self.farm = Farm.objects.create(owner=self.user, name='Feed farm', location='Test',
            established_date=date(2026, 1, 1), contact_email='feed@example.com', contact_phone='123')
        self.branch = Branch.objects.create(farm=self.farm, name='Main')
        self.client.force_login(self.user)

    def test_feed_purchase_appears_once_and_distribution_does_not_reduce_cost(self):
        added = self.client.post(reverse('inventory-list'), {
            'item_type': 'feed', 'name': 'Feed purchase', 'quantity': '100', 'unit': 'kg',
            'cost_per_unit': '50', 'date_added': '2026-11-12',
        })
        self.assertEqual(added.status_code, 201)
        item = Inventory.objects.get(pk=added.json()['id'])
        Expense.objects.create(user=self.user, branch=self.branch, expense_type='feed',
            description='Separate feed expense', amount=250, date=date(2026, 11, 12))
        Inventory.objects.create(user=self.user, item_type='medicine', name='Medicine', quantity=2,
            unit='bottle', cost_per_unit=100, date_added=date(2026, 11, 12))
        for distributed in (False, True):
            if distributed:
                distribution = self.client.post(reverse('inventory-distribution-list'), {
                    'inventory': item.pk, 'branch': self.branch.pk, 'quantity': '20', 'date': '2026-11-12',
                })
                self.assertEqual(distribution.status_code, 201)
            response = self.client.get(reverse('dashboard'), {'month': 11, 'year': 2026})
            self.assertEqual(response.context['metrics']['feed_cost'], Decimal('5250'))
            self.assertEqual(response.context['metrics']['inventory_feed_cost'], Decimal('5000'))
            self.assertEqual(response.context['metrics']['expenses'], Decimal('5450'))
            self.assertEqual(response.context['chart_data']['feed'][-1], 5250.)
            self.assertNotContains(response, 'in inventory feed purchases')
        item.refresh_from_db()
        self.assertEqual(item.total_value, Decimal('4000'))
        self.assertEqual(Expense.objects.filter(user=self.user, category='inventory', expense_type='feed').count(), 1)

    def test_branch_view_shows_farm_purchase_cost_without_misattributing_it(self):
        Inventory.objects.create(user=self.user, item_type='feed', name='Current feed', quantity=10,
            unit='kg', cost_per_unit=50, date_added=date(2026, 11, 12))
        Inventory.objects.create(user=self.user, item_type='feed', name='Old feed', quantity=100,
            unit='kg', cost_per_unit=50, date_added=date(2026, 10, 12))
        neighbor = get_user_model().objects.create_user(username='feed-dashboard-neighbor', password='password123')
        Inventory.objects.create(user=neighbor, item_type='feed', name='Private feed', quantity=100,
            unit='kg', cost_per_unit=50, date_added=date(2026, 11, 12))
        response = self.client.get(reverse('dashboard'), {'branch': self.branch.pk, 'month': 11, 'year': 2026})
        self.assertEqual(response.context['metrics']['feed_cost'], 0)
        self.assertEqual(response.context['metrics']['inventory_feed_cost'], Decimal('500'))
        self.assertContains(response, 'Farm-wide inventory feed purchases:')
        self.assertContains(response, 'View farm-wide feed cost')
        self.assertContains(response, 'month=11&amp;year=2026')


class BranchScopedFlockIdTests(TestCase):
    def test_flock_ids_can_repeat_across_branches_but_not_within_one(self):
        user = get_user_model().objects.create_user(username='flock-branch-owner', password='password123')
        farm = Farm.objects.create(
            owner=user,
            name='Flock ID Farm',
            location='Main City',
            established_date=date(2024, 1, 1),
            contact_email='flocks@example.com',
            contact_phone='09123456789',
        )
        labogon = Branch.objects.create(farm=farm, name='Labogon')
        mandaue = Branch.objects.create(farm=farm, name='Mandaue')
        self.client.force_login(user)
        endpoint = reverse('flock-list')

        for branch in (labogon, mandaue):
            response = self.client.post(
                endpoint,
                {
                    'branch': branch.pk,
                    'flock_id': '01',
                    'breed': 'layers',
                    'quantity': 20,
                    'status': 'active',
                },
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 201, response.content)

        duplicate_response = self.client.post(
            endpoint,
            {
                'branch': labogon.pk,
                'flock_id': '01',
                'breed': 'layers',
                'quantity': 15,
                'status': 'active',
            },
            content_type='application/json',
        )

        self.assertEqual(duplicate_response.status_code, 400)
        self.assertIn('flock_id', duplicate_response.json())


class MortalityProductionDisplayTests(TestCase):
    def test_production_page_shows_flock_balance_after_mortality(self):
        user = get_user_model().objects.create_user(username='mortality-production', password='password123')
        flock = Flock.objects.create(
            user=user,
            flock_id='LAYERS-01',
            breed='layers',
            quantity=20,
            status='active',
        )
        ProductionRecord.objects.create(
            user=user,
            flock=flock,
            product_type='eggs',
            quantity=10,
            unit='eggs',
            date=date(2026, 10, 20),
        )
        MortalityRecord.objects.create(
            user=user,
            flock=flock,
            quantity=3,
            reason='disease',
            date=date(2026, 10, 21),
        )
        self.client.force_login(user)

        response = self.client.get(reverse('production_records'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Current Birds Remaining')
        self.assertContains(response, '<td>17</td>', html=True)
        self.assertContains(response, '<td>10</td>', html=True)
        self.assertNotContains(response, '<th>Notes</th>', html=True)


class InventoryDistributionTests(TestCase):
    def test_distribution_records_branch_and_date_and_reduces_stock(self):
        user = get_user_model().objects.create_user(username='inventory-distributor', password='password123')
        farm = Farm.objects.create(
            owner=user,
            name='Distribution Farm',
            location='Main City',
            established_date=date(2024, 1, 1),
            contact_email='distribution@example.com',
            contact_phone='09123456789',
        )
        branch = Branch.objects.create(farm=farm, name='North Branch')
        inventory = Inventory.objects.create(
            user=user,
            item_type='feed',
            name='Layer feed',
            quantity=Decimal('10.00'),
            unit='kg',
            cost_per_unit=Decimal('25.00'),
        )
        self.client.force_login(user)
        endpoint = reverse('inventory-distribution-list')
        response = self.client.post(
            endpoint,
            {
                'inventory': inventory.pk,
                'branch': branch.pk,
                'quantity': '3.50',
                'date': '2026-10-20',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201, response.content)
        inventory.refresh_from_db()
        distribution = InventoryDistribution.objects.get(inventory=inventory)
        self.assertEqual(inventory.quantity, Decimal('6.50'))
        self.assertEqual(inventory.total_value, Decimal('162.50'))
        self.assertEqual(distribution.branch, branch)
        self.assertEqual(distribution.date, date(2026, 10, 20))

        history_response = self.client.get(endpoint, {'inventory': inventory.pk})

        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response.data['results'][0]['branch_name'], 'North Branch')
        self.assertEqual(history_response.data['results'][0]['quantity'], '3.50')

    def test_distribution_cannot_exceed_available_stock(self):
        user = get_user_model().objects.create_user(username='inventory-limited', password='password123')
        farm = Farm.objects.create(
            owner=user,
            name='Limited Farm',
            location='Main City',
            established_date=date(2024, 1, 1),
            contact_email='limited@example.com',
            contact_phone='09123456789',
        )
        branch = Branch.objects.create(farm=farm, name='South Branch')
        inventory = Inventory.objects.create(
            user=user,
            item_type='feed',
            name='Starter feed',
            quantity=Decimal('2.00'),
            unit='kg',
            cost_per_unit=Decimal('20.00'),
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('inventory-distribution-list'),
            {
                'inventory': inventory.pk,
                'branch': branch.pk,
                'quantity': '3.00',
                'date': '2026-10-21',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        inventory.refresh_from_db()
        self.assertEqual(inventory.quantity, Decimal('2.00'))
        self.assertFalse(InventoryDistribution.objects.exists())


class InventoryPurchaseDateTests(TestCase):
    def test_inventory_page_displays_purchase_record_date(self):
        user = get_user_model().objects.create_user(username='inventory-date-viewer', password='password123')
        self.client.force_login(user)

        response = self.client.get(reverse('inventory'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Date Purchased/Recorded')
        self.assertContains(response, 'name="date_added"')

    def test_inventory_purchase_date_is_saved_and_used_for_purchase_expense(self):
        user = get_user_model().objects.create_user(username='inventory-date-owner', password='password123')
        self.client.force_login(user)

        response = self.client.post(
            reverse('inventory-list'),
            {
                'item_type': 'feed',
                'name': 'Dated feed',
                'date_added': '2026-10-12',
                'quantity': '4',
                'unit': 'bags',
                'cost_per_unit': '50.00',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201, response.content)
        item = Inventory.objects.get(user=user, name='Dated feed')
        expense = Expense.objects.get(description='Inventory purchase: Dated feed')
        self.assertEqual(item.date_added, date(2026, 10, 12))
        self.assertEqual(expense.date, date(2026, 10, 12))


class ProductionProductTypeTests(TestCase):
    def test_product_type_matches_flock_breed(self):
        user = get_user_model().objects.create_user(username='production-owner', password='password123')
        layers = Flock.objects.create(
            user=user,
            flock_id='LAYERS-001',
            breed='layers',
            quantity=20,
            status='active',
        )
        broilers = Flock.objects.create(
            user=user,
            flock_id='BROILERS-001',
            breed='broilers',
            quantity=20,
            status='active',
        )

        layers_form = ProductionRecordForm({
            'flock': layers.pk,
            'product_type': 'eggs',
            'quantity': '10',
            'unit': 'eggs',
            'date': '2026-09-13',
        }, user=user)
        broilers_form = ProductionRecordForm({
            'flock': broilers.pk,
            'product_type': 'meat_ready',
            'quantity': '10',
            'unit': 'birds',
            'date': '2026-09-13',
        }, user=user)

        self.assertTrue(layers_form.is_valid(), layers_form.errors)
        self.assertTrue(broilers_form.is_valid(), broilers_form.errors)
        self.assertEqual([value for value, _ in layers_form.fields['product_type'].choices], ['eggs', 'meat_ready'])

    def test_production_form_only_accepts_flock_from_selected_branch(self):
        user = get_user_model().objects.create_user(username='production-branch-owner', password='password123')
        farm = Farm.objects.create(
            owner=user,
            name='Production Farm',
            location='Main City',
            established_date=date(2024, 1, 1),
            contact_email='production@example.com',
            contact_phone='09123456789',
        )
        north = Branch.objects.create(farm=farm, name='North Branch')
        south = Branch.objects.create(farm=farm, name='South Branch')
        north_flock = Flock.objects.create(
            user=user, branch=north, flock_id='01', breed='layers', quantity=50,
        )
        south_flock = Flock.objects.create(
            user=user, branch=south, flock_id='01', breed='layers', quantity=40,
        )
        form_data = {
            'branch': north.pk,
            'flock': south_flock.pk,
            'product_type': 'eggs',
            'quantity': 10,
            'unit': 'eggs',
            'date': '2026-10-21',
            'notes': '',
        }

        form = ProductionRecordForm(form_data, user=user)

        self.assertFalse(form.is_valid())
        self.assertIn('flock', form.errors)
        self.assertIn(f'data-branch-id="{north.pk}"', str(form['flock']))
        self.assertIn(f'data-branch-id="{south.pk}"', str(form['flock']))


class TransactionRecordTests(TestCase):
    def test_revenue_creates_transaction_record(self):
        revenue = Revenue.objects.create(
            revenue_type='eggs',
            quantity=Decimal('12'),
            unit='tray',
            price_per_unit=Decimal('180'),
            date=date(2026, 7, 4),
            notes='Morning sale',
        )

        transaction = TransactionRecord.objects.get(source_object_id=revenue.pk)

        self.assertEqual(transaction.transaction_type, 'income')
        self.assertEqual(transaction.action, 'created')
        self.assertEqual(transaction.amount, revenue.total_amount)
        self.assertEqual(transaction.transaction_date, revenue.date)

    def test_expense_creates_transaction_record(self):
        expense = Expense.objects.create(
            expense_type='feed',
            description='Layer feed',
            amount=Decimal('1250.00'),
            date=date(2026, 7, 4),
            category='supplies',
        )

        transaction = TransactionRecord.objects.get(source_object_id=expense.pk)

        self.assertEqual(transaction.transaction_type, 'expense')
        self.assertEqual(transaction.action, 'created')
        self.assertEqual(transaction.amount, expense.amount)
        self.assertEqual(transaction.description, expense.description)

    def test_inventory_create_creates_matching_expense(self):
        item = Inventory.objects.create(
            item_type='feed',
            name='Chicken Feeds',
            quantity=Decimal('10'),
            unit='kg',
            cost_per_unit=Decimal('125.00'),
        )

        expense = Expense.objects.get(description='Inventory purchase: Chicken Feeds')

        self.assertEqual(expense.expense_type, item.item_type)
        self.assertEqual(expense.amount, Decimal('1250.00'))
        self.assertEqual(expense.date, item.date_added)
        self.assertEqual(expense.category, 'inventory')

    def test_inventory_delete_deletes_matching_expense(self):
        item = Inventory.objects.create(
            item_type='other',
            name='Hen House',
            quantity=Decimal('1'),
            unit='units',
            cost_per_unit=Decimal('5000.00'),
        )
        expense = Expense.objects.get(description='Inventory purchase: Hen House')

        item.delete()

        self.assertFalse(Inventory.objects.filter(pk=item.pk).exists())
        self.assertFalse(Expense.objects.filter(pk=expense.pk).exists())

    def test_expense_create_does_not_create_inventory_item(self):
        Expense.objects.create(
            expense_type='feed',
            description='Manual feed expense',
            amount=Decimal('750.00'),
            date=date(2026, 7, 5),
            category='manual',
        )

        self.assertFalse(Inventory.objects.exists())


class RoosterAgeEstimatorTests(TestCase):
    def setUp(self):
        self.detector_patch = patch('core.chicken_detection.load_detector', return_value=None)
        self.detector_patch.start()
        self.addCleanup(self.detector_patch.stop)
        self.anatomy_patch = patch('core.poultry_vision.load_vision_models', return_value=None)
        self.anatomy_patch.start()
        self.addCleanup(self.anatomy_patch.stop)
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.user = get_user_model().objects.create_user(
            username='tester',
            password='password123',
        )
        self.client.force_login(self.user)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_opening_estimator_does_not_import_heavy_model_runtimes(self):
        import builtins
        original_import = builtins.__import__

        def reject_model_import(name, *args, **kwargs):
            if name in ('core.rooster_age_classifier', 'torch', 'transformers', 'ultralytics'):
                raise AssertionError('Opening the estimator tried to load an ML runtime: ' + name)
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=reject_model_import):
            response = self.client.get(reverse('rooster_age_estimator'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Model availability is checked when you submit')

    def test_finetuned_model_comparison_keeps_original_prediction_and_checkpoint(self):
        from pathlib import Path
        import hashlib
        from core.age_model_registry import candidate_entry
        if candidate_entry() is None:
            self.skipTest('Comparison weights are not installed')
        root = Path(__file__).resolve().parents[2]
        original_path = root / 'spur_age/models/spur_age_model.pth'
        original_hash = hashlib.sha256(original_path.read_bytes()).hexdigest()
        response = self.client.post(reverse('rooster_age_estimator'), {
            'age_model': 'finetuned',
            'photos': [SimpleUploadedFile('arbitrary-name.jpg', (root / 'spurs images/4months.jpg').read_bytes(), content_type='image/jpeg')],
        })
        self.assertEqual(response.status_code, 200)
        record = RoosterAgeEstimate.objects.get()
        self.assertEqual(record.analysis['age_model'], 'finetuned')
        self.assertEqual(record.analysis['age_prediction']['model_variant'], 'finetuned')
        self.assertLess(abs(record.analysis['age_prediction']['age_months']-3), 1)
        self.assertGreater(record.analysis['original_age_prediction']['age_months'], 7)
        self.assertNotContains(response, 'Original-model estimate:')
        saved = self.client.get(reverse('rooster_age_estimator'), {'estimate': record.pk})
        self.assertEqual(saved.context['selected_age_model'], 'finetuned')
        self.assertEqual(hashlib.sha256(original_path.read_bytes()).hexdigest(), original_hash)

    def test_saves_only_uploaded_rooster_photos(self):
        photo = SimpleUploadedFile(
            'rooster.jpg',
            b'fake image bytes',
            content_type='image/jpeg',
        )

        response = self.client.post(reverse('rooster_age_estimator'), {
            'photos': [photo],
            'spur_visibility': ['clear', 'clear'],
            'spur_length': ['short', 'long'],
            'spur_thickness': ['thin', 'thick'],
            'spur_point_shape': ['rounded', 'pointed'],
            'spur_curvature': ['straight', 'curved'],
            'secondary_clues': ['', 'extra blank card'],
        })

        self.assertEqual(response.status_code, 200)
        estimates = RoosterAgeEstimate.objects.filter(user=self.user)
        self.assertEqual(estimates.count(), 1)
        self.assertEqual(estimates.first().photo_name, 'rooster.jpg')
        self.assertTrue(estimates.first().photo)
        self.assertEqual(estimates.first().estimated_age_range, 'Insufficient evidence')
        self.assertEqual(estimates.first().spur_visibility, 'unassessed')

    def test_image_result_does_not_claim_unvalidated_visual_analysis(self):
        image_bytes = BytesIO()
        Image.effect_noise((900, 700), 100).convert('RGB').save(image_bytes, format='JPEG')
        image_bytes.seek(0)
        photo = SimpleUploadedFile(
            'clear-rooster.jpg',
            image_bytes.read(),
            content_type='image/jpeg',
        )

        response = self.client.post(reverse('rooster_age_estimator'), {
            'photos': [photo],
            'spur_visibility': ['clear'],
            'spur_length': ['medium'],
            'spur_thickness': ['moderate'],
            'spur_point_shape': ['pointed'],
            'spur_curvature': ['slight'],
            'secondary_clues': ['large comb and adult feathers'],
        })

        self.assertEqual(response.status_code, 200)
        result = response.context['results'][0]
        self.assertEqual(result['chicken_detected'], 'Chicken not detected')
        self.assertIn('no chicken detector is configured', result['chicken_location_assessment'])
        self.assertIn('unavailable', result['leg_detection_status'])
        self.assertIn('unavailable', result['spur_detection_status'])
        self.assertEqual(result['spur_visibility'], 'Not assessed')
        self.assertTrue(result['estimated_age_range'].startswith('Experimental estimate:'))
        self.assertEqual(result['confidence'], 'Uncalibrated experimental estimate')
        self.assertIn('separate experimental predictions', result['spur_observations'])
        self.assertIn('Technical image quality', result['image_assessment'])
        self.assertIn('does not detect chickens or spurs', result['limitations'])

    def test_page_no_longer_requests_manual_spur_observations(self):
        response = self.client.get(reverse('rooster_age_estimator'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'accuracy on unseen chickens is not established.')
        self.assertNotContains(response, 'name="experimental_closeup"')
        self.assertContains(response, 'Estimate Age')
        self.assertNotContains(response, 'name="spur_visibility"')
        self.assertNotContains(response, 'name="spur_length"')
        self.assertNotContains(response, 'name="secondary_clues"')

    def test_chicken_detection_is_saved_separately_from_experimental_age(self):
        from core.rooster_age_classifier import predict_rooster_age
        stream = BytesIO()
        Image.effect_noise((900, 700), 100).convert('RGB').save(stream, format='JPEG')
        output = {'status': 'detected', 'boxes': [{'xyxy': [10, 20, 300, 400], 'score': 0.8}],
                  'message': 'Box [10, 20, 300, 400] pixels; detector score 0.800'}
        with patch('core.chicken_detection.detect_chicken', return_value=output), \
             patch('core.rooster_age_classifier.predict_rooster_age', wraps=predict_rooster_age) as predict:
            response = self.client.post(reverse('rooster_age_estimator'), {
                'photos': [SimpleUploadedFile('chicken.jpg', stream.getvalue(), content_type='image/jpeg')],
            })
        result = response.context['results'][0]
        self.assertEqual(result['chicken_detected'], 'Yes')
        self.assertEqual(result['chicken_boxes'], output['boxes'])
        self.assertIn(output['message'], RoosterAgeEstimate.objects.get().spur_observations)
        self.assertTrue(result['estimated_age_range'].startswith('Experimental estimate:'))
        self.assertEqual(result['spur_visibility'], 'Not assessed')
        predict.assert_called_once()

    def test_real_age_model_upload_ignores_filenames_and_keeps_detection_unassessed(self):
        from pathlib import Path
        photo_path = Path(__file__).resolve().parents[2] / 'spur_age/dataset/images/10months (1).jpg'
        self.assertTrue(photo_path.is_file(), 'The audited real photograph must be available for this integration check.')
        content = photo_path.read_bytes()
        predictions = []
        for filename in ('1months.jpg', '24months.jpg'):
            response = self.client.post(reverse('rooster_age_estimator'), {
                'photos': [SimpleUploadedFile(filename, content, content_type='image/jpeg')],
            })
            self.assertEqual(response.status_code, 200)
            result = response.context['results'][0]
            record = RoosterAgeEstimate.objects.get(pk=result['id'])
            prediction = record.analysis['age_prediction']
            self.assertIsNotNone(prediction)
            self.assertGreaterEqual(prediction['age_months'], 1)
            self.assertLessEqual(prediction['age_months'], 24)
            predictions.append(prediction['age_months'])
            self.assertEqual(record.analysis['age_prediction_status'], 'experimental')
            self.assertEqual(record.analysis['spur_detection']['status'], 'unavailable')
            self.assertEqual(record.spur_visibility, 'unassessed')
            self.assertEqual(record.chicken_detected, 'unassessed')
            self.assertEqual(len(prediction['model_sha256']), 64)
            self.assertIn('not independent validation', result['model_evaluation'])
        self.assertEqual(predictions[0], predictions[1])

    def test_does_not_predict_unreadable_upload(self):
        with patch('core.rooster_age_classifier.predict_rooster_age') as predict:
            response = self.client.post(reverse('rooster_age_estimator'), {
                'photos': [SimpleUploadedFile('bad.jpg', b'not an image', content_type='image/jpeg')],
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['results'][0]['estimated_age_range'], 'Insufficient evidence')
        predict.assert_not_called()

    @override_settings(DEBUG=False)
    def test_bright_photo_predicts_by_default_and_preview_works_without_debug(self):
        from pathlib import Path
        source = Path(__file__).resolve().parents[2] / 'spurs images/3monthsss.jpg'
        content = source.read_bytes()
        response = self.client.post(reverse('rooster_age_estimator'), {
            'photos': [SimpleUploadedFile('bright-spur.jpg', content, content_type='image/jpeg')],
        })
        self.assertEqual(response.status_code, 200)
        result = response.context['results'][0]
        record = RoosterAgeEstimate.objects.get(pk=result['id'])
        self.assertEqual(record.analysis['image_quality']['quality'], 'limited')
        self.assertIn('too bright', record.analysis['image_quality']['summary'])
        self.assertTrue(result['estimated_age_range'].startswith('Experimental estimate:'))
        self.assertIn('Image quality warning:', result['limitations'])
        self.assertIsNotNone(record.analysis['age_prediction'])
        self.assertEqual(record.analysis['input_mode'], 'experimental_image_estimate')
        self.assertEqual(record.spur_visibility, 'unassessed')
        self.assertEqual(result['photo_url'], reverse('rooster_estimate_photo', args=[record.pk]))
        preview = self.client.get(result['photo_url'])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview['Content-Type'], 'image/jpeg')
        self.assertEqual(b''.join(preview.streaming_content), content)
        preview.close()

    def test_photo_preview_is_private_and_requires_a_readable_file(self):
        response = self.client.post(reverse('rooster_age_estimator'), {
            'photos': [SimpleUploadedFile('bad.jpg', b'broken image bytes', content_type='image/jpeg')],
        })
        record = RoosterAgeEstimate.objects.get()
        url = reverse('rooster_estimate_photo', args=[record.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(response.context['results'][0]['photo_url'], '')

        # Use a valid image so a 404 for another user proves authorization,
        # rather than merely rejecting the corrupt file above.
        from pathlib import Path
        content = (Path(__file__).resolve().parents[2] / 'spurs images/3monthsss.jpg').read_bytes()
        record.photo.save('private.jpg', SimpleUploadedFile('private.jpg', content, content_type='image/jpeg'))
        owner_preview = self.client.get(url)
        self.assertEqual(owner_preview.status_code, 200)
        owner_preview.close()
        other_user = get_user_model().objects.create_user(username='other-photo-owner', password='password123')
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertRedirects(self.client.get(url), f'{reverse("login")}?next={url}', fetch_redirect_response=False)

    def test_missing_photo_and_model_failures_have_specific_reasons(self):
        from pathlib import Path
        content = (Path(__file__).resolve().parents[2] / 'spurs images/3monthsss.jpg').read_bytes()
        with patch('core.rooster_age_classifier.model_is_ready', return_value=False):
            response = self.client.post(reverse('rooster_age_estimator'), {
                'photos': [SimpleUploadedFile('readable.jpg', content, content_type='image/jpeg')],
            })
        result = response.context['results'][0]
        self.assertIn('age model could not be loaded', result['spur_observations'])
        self.assertNotIn('quality checks did not pass', result['spur_observations'])
        record = RoosterAgeEstimate.objects.get(pk=result['id'])
        record.photo.storage.delete(record.photo.name)
        self.assertEqual(self.client.get(result['photo_url']).status_code, 404)

        with patch('core.rooster_age_classifier.predict_rooster_age', return_value=None):
            failed = self.client.post(reverse('rooster_age_estimator'), {
                'photos': [SimpleUploadedFile('readable-again.jpg', content, content_type='image/jpeg')],
            })
        self.assertIn('could not generate a prediction', failed.context['results'][0]['spur_observations'])

    def test_reanalysis_preserves_original_and_checks_ownership(self):
        content = BytesIO()
        Image.new('RGB', (320, 320), 'white').save(content, format='JPEG')
        self.client.post(reverse('rooster_age_estimator'), {
            'photos': [SimpleUploadedFile('saved.jpg', content.getvalue(), content_type='image/jpeg')],
        })
        original = RoosterAgeEstimate.objects.get()
        original_analysis = original.analysis
        response = self.client.post(reverse('rooster_age_estimator'), {'reanalyze_estimate_id': str(original.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RoosterAgeEstimate.objects.count(), 2)
        latest = RoosterAgeEstimate.objects.exclude(pk=original.pk).get()
        self.assertEqual(latest.analysis['reanalysis_of'], original.pk)
        self.assertIn(f'estimate={latest.pk}', response.url)
        original.refresh_from_db()
        self.assertEqual(original.analysis, original_analysis)
        saved = self.client.get(response.url)
        self.assertContains(saved, 'You are viewing a saved analysis')
        self.assertContains(saved, 'Analyze again with current models')
        other = get_user_model().objects.create_user(username='other-reanalysis', password='password123')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('rooster_age_estimator'), {'reanalyze_estimate_id': str(original.pk)}).status_code, 404)
        self.assertEqual(RoosterAgeEstimate.objects.count(), 2)

    def test_saved_anatomy_analysis_is_viewable_without_rerunning_models(self):
        from pathlib import Path
        content = (Path(__file__).resolve().parents[2] / 'spurs images/3monthsss.jpg').read_bytes()
        anatomy = {
            'status': 'completed', 'image_width': 598, 'image_height': 513,
            'legs': [{'xyxy': [10, 20, 120, 450], 'score': .8}],
            'spurs': [{'xyxy': [100, 150, 200, 250], 'score': .7}],
            'masks': [{'xyxy': [100, 150, 200, 250], 'polygon': [[100, 150], [200, 150], [150, 250]], 'score': .75}],
            'measurements': [{'length_px': 80., 'physical_length_cm': 8., 'truncated_at_frame': False,
                              'centerline': [[120, 160], [150, 230]], 'mask_index': 0}],
            'message': 'Experimental anatomy outputs.',
        }
        with patch('core.poultry_vision.analyze_poultry', return_value=anatomy) as predict:
            response = self.client.post(reverse('rooster_age_estimator'), {
                'pixels_per_cm': '10',
                'photos': [SimpleUploadedFile('spur.jpg', content, content_type='image/jpeg')],
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(predict.call_args.args[1], 10.)
        record = RoosterAgeEstimate.objects.get()
        self.assertEqual(record.analysis['anatomy'], anatomy)
        self.assertEqual(record.chicken_detected, 'unassessed')
        self.assertEqual(record.spur_visibility, 'clear')
        with patch('core.poultry_vision.analyze_poultry') as rerun, patch('core.rooster_age_classifier.predict_rooster_age') as age_rerun:
            saved = self.client.get(reverse('rooster_age_estimator'), {'estimate': record.pk})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.context['results'][0]['overlay']['masks'], anatomy['masks'])
        self.assertContains(saved, '8.00 cm using your supplied scale')
        rerun.assert_not_called()
        age_rerun.assert_not_called()
        other_user = get_user_model().objects.create_user(username='other-anatomy-owner', password='password123')
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(reverse('rooster_age_estimator'), {'estimate': record.pk}).status_code, 404)

    def test_invalid_or_batch_calibration_does_not_produce_centimeter_values(self):
        from pathlib import Path
        content = (Path(__file__).resolve().parents[2] / 'spurs images/3monthsss.jpg').read_bytes()
        from core.poultry_vision import analyze_poultry
        for scale, count in [('nan', 1), ('-1', 1), ('10', 2)]:
            with patch('core.poultry_vision.analyze_poultry', wraps=analyze_poultry) as predict:
                response = self.client.post(reverse('rooster_age_estimator'), {
                    'pixels_per_cm': scale,
                    'photos': [SimpleUploadedFile(f'spur-{i}.jpg', content, content_type='image/jpeg') for i in range(count)],
                })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(all(call.args[1] is None for call in predict.call_args_list))


class AnalyticsForecastTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='owner', password='password123')
        self.other_user = User.objects.create_user(username='neighbor', password='password123')

    def test_revenue_forecast_uses_only_logged_in_users_actual_revenue(self):
        today = timezone.localdate()
        Revenue.objects.create(
            user=self.user,
            revenue_type='eggs',
            quantity=Decimal('10'),
            unit='tray',
            price_per_unit=Decimal('100'),
            date=today,
        )
        Revenue.objects.create(
            user=self.other_user,
            revenue_type='eggs',
            quantity=Decimal('10'),
            unit='tray',
            price_per_unit=Decimal('900'),
            date=today,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('analytics'))

        self.assertEqual(response.status_code, 200)
        actual_revenue = response.context['chart_data']['actualVsPredicted']['actualRevenue']
        predicted_revenue = response.context['chart_data']['actualVsPredicted']['predictedRevenue']
        self.assertIn(1000.0, actual_revenue)
        self.assertNotIn(9000.0, actual_revenue)
        self.assertEqual([value for value in predicted_revenue if value is not None], [1000.0] * 6)
        self.assertFalse(Prediction.objects.filter(user=self.other_user, predicted_value=1000).exists())


class ForecastingPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='forecaster', password='password123')
        self.other_user = User.objects.create_user(username='other-forecaster', password='password123')

    def test_forecasting_page_uses_logged_in_users_encoded_data(self):
        today = timezone.localdate()
        flock = Flock.objects.create(
            user=self.user,
            flock_id='LAYER-1',
            breed='layers',
            quantity=20,
            status='active',
        )
        Revenue.objects.create(
            user=self.user,
            revenue_type='eggs',
            quantity=Decimal('10'),
            unit='tray',
            price_per_unit=Decimal('100'),
            date=today,
        )
        Revenue.objects.create(
            user=self.other_user,
            revenue_type='eggs',
            quantity=Decimal('10'),
            unit='tray',
            price_per_unit=Decimal('900'),
            date=today,
        )
        Expense.objects.create(
            user=self.user,
            expense_type='feed',
            description='Layer feed',
            amount=Decimal('300.00'),
            date=today,
        )
        ProductionRecord.objects.create(
            user=self.user,
            flock=flock,
            product_type='eggs',
            quantity=Decimal('55'),
            unit='eggs',
            date=today,
        )
        Inventory.objects.create(
            user=self.user,
            item_type='feed',
            name='Layer mash',
            quantity=Decimal('40'),
            unit='kg',
            cost_per_unit=Decimal('25'),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('forecasting'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['revenue_forecast'], 1000.0)
        self.assertEqual(response.context['expected_profit'], -300.0)
        self.assertEqual(response.context['feed_demand'], 72.0)
        self.assertEqual(response.context['feed_stock'], Decimal('40'))
        self.assertEqual(response.context['production_forecast'], 55.0)
        self.assertNotIn(9000.0, response.context['chart_data']['actualRevenue'])


class ScenarioAnalysisPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='scenario-owner', password='password123')
        self.other_user = User.objects.create_user(username='scenario-other', password='password123')

    def test_scenario_analysis_uses_logged_in_users_encoded_data(self):
        today = timezone.localdate()
        Revenue.objects.create(
            user=self.user,
            revenue_type='eggs',
            quantity=Decimal('10'),
            unit='tray',
            price_per_unit=Decimal('100'),
            date=today,
        )
        Revenue.objects.create(
            user=self.other_user,
            revenue_type='eggs',
            quantity=Decimal('10'),
            unit='tray',
            price_per_unit=Decimal('900'),
            date=today,
        )
        Expense.objects.create(
            user=self.user,
            expense_type='feed',
            description='Layer feed',
            amount=Decimal('300.00'),
            date=today,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('scenario_analysis'))

        self.assertEqual(response.status_code, 200)
        metrics = response.context['scenario_metrics']
        self.assertEqual(metrics['revenue'], Decimal('1000.00'))
        self.assertEqual(metrics['expenses'], Decimal('300.00'))
        self.assertEqual(metrics['profit'], Decimal('700.00'))
        self.assertEqual(metrics['feed_cost'], Decimal('300.00'))
        self.assertEqual(metrics['predicted_revenue'], 1000.0 / 3)
        self.assertEqual(metrics['predicted_expenses'], 100.0)
        self.assertEqual(metrics['predicted_profit'], 1000.0 / 3 - 100.0)
        self.assertEqual(len(response.context['monthly_profit']), 6)
        self.assertNotContains(response, '120,000.00')
        self.assertNotContains(response, '9,000.00')


class ReportDownloadTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='report-owner', password='password123')
        self.other_user = User.objects.create_user(username='report-other', password='password123')

    def test_report_download_exports_logged_in_users_data_as_csv(self):
        today = timezone.localdate()
        report = Report.objects.create(
            user=self.user,
            report_type='daily',
            title='Daily Report',
            start_date=today,
            end_date=today,
        )
        Revenue.objects.create(
            user=self.user,
            revenue_type='eggs',
            quantity=Decimal('10'),
            unit='tray',
            price_per_unit=Decimal('100'),
            date=today,
            notes='Owner sale',
        )
        Revenue.objects.create(
            user=self.other_user,
            revenue_type='eggs',
            quantity=Decimal('10'),
            unit='tray',
            price_per_unit=Decimal('900'),
            date=today,
            notes='Other sale',
        )
        Expense.objects.create(
            user=self.user,
            expense_type='feed',
            description='Owner feed',
            amount=Decimal('300.00'),
            date=today,
        )

        self.client.force_login(self.user)
        response = self.client.get(f'/api/reports/{report.id}/download/')
        csv_text = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="daily_report_', response['Content-Disposition'])
        self.assertIn('SMARTPOULTRY Report Export', csv_text)
        self.assertIn('Owner sale', csv_text)
        self.assertIn('Owner feed', csv_text)
        self.assertIn('1000.00', csv_text)
        self.assertIn('Monthly Financial Summary', csv_text)
        self.assertIn('Profit', csv_text)
        self.assertNotIn('Other sale', csv_text)
        self.assertNotIn('9000.00', csv_text)
