from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from flocks.models import Flock
from production.models import ProductionRecord
from revenue.models import Revenue
from expenses.models import Expense


class AnalyticsActualValueTests(TestCase):
    def test_actual_table_uses_owned_recorded_totals_and_keeps_units_separate(self):
        user=get_user_model().objects.create_user(username='actual-values-owner')
        other=get_user_model().objects.create_user(username='actual-values-other')
        today=timezone.localdate()
        Revenue.objects.create(user=user,revenue_type='eggs',quantity=10,price_per_unit=100,date=today)
        Expense.objects.create(user=user,expense_type='feed',description='Feed',amount=250,date=today)
        Revenue.objects.create(user=other,revenue_type='eggs',quantity=99,price_per_unit=100,date=today)
        flock=Flock.objects.create(user=user,flock_id='A',breed='layers',quantity=10)
        another=Flock.objects.create(user=user,flock_id='B',breed='layers',quantity=10)
        ProductionRecord.objects.create(user=user,flock=flock,product_type='eggs',quantity=20,unit='eggs',date=today)
        ProductionRecord.objects.create(user=user,flock=another,product_type='eggs',quantity=2,unit='trays',date=today)
        Revenue.objects.create(user=user,revenue_type='eggs',quantity=100,price_per_unit=100,date=today+timedelta(days=1))
        self.client.force_login(user)
        response=self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code,200)
        rows=response.context['actual_records']
        self.assertEqual(next(row['value'] for row in rows if row['type']=='Profit'),Decimal('750'))
        self.assertEqual({(row['unit'],row['value']) for row in rows if row['type']=='Egg Production'},{('eggs',Decimal('20')),('trays',Decimal('2'))})
        self.assertContains(response,'Actual Recorded Values')
        self.assertContains(response,'Actual Value')
        self.assertNotContains(response,'<th>Predicted Value</th>',html=True)

    def test_no_logged_data_does_not_display_generated_forecasts_as_actual(self):
        user=get_user_model().objects.create_user(username='actual-values-empty')
        self.client.force_login(user)
        response=self.client.get(reverse('analytics'))
        self.assertEqual(response.context['actual_records'],[])
        self.assertContains(response,'No actual records available')
