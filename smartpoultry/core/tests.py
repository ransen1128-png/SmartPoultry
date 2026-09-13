from datetime import date
from decimal import Decimal
from io import BytesIO
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from analytics.models import Prediction
from core.models import RoosterAgeEstimate, TransactionRecord, Farm, Branch
from expenses.models import Expense
from flocks.models import Flock
from inventory.models import Inventory
from PIL import Image
from production.models import ProductionRecord, MortalityRecord
from core.forms import ProductionRecordForm
from reports.models import Report
from revenue.models import Revenue


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

    def test_uploaded_photo_quality_is_used_in_age_result(self):
        image_bytes = BytesIO()
        Image.new('RGB', (900, 700), color=(160, 150, 120)).save(image_bytes, format='JPEG')
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
        self.assertIn('Photo', result['image_assessment'])
        self.assertIn('Image quality:', result['spur_observations'])
        self.assertIn('Image check:', result['reasoning'])


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
