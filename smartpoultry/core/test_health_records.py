from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from expenses.models import Expense
from flocks.models import Flock
from production.models import HealthRecord


class RetiredHealthRecordsTests(TestCase):
    def test_health_records_are_unavailable_and_existing_data_is_preserved(self):
        owner = get_user_model().objects.create_user('farm-owner')
        flock = Flock.objects.create(user=owner, flock_id='01', breed='layers', quantity=10)
        date = timezone.localdate()
        record = HealthRecord.objects.create(flock=flock, date=date)
        expense = Expense.objects.create(
            user=owner, expense_type='medicine', description='Medicine purchase', amount=25, date=date,
        )
        self.client.force_login(owner)

        self.assertNotContains(self.client.get(reverse('settings')), 'Health Records')
        self.assertContains(self.client.get(reverse('expenses')), 'Medicine')
        for path in (
            '/health-records/',
            '/health-records/add/',
            f'/health-records/{record.pk}/edit/',
            f'/health-records/{record.pk}/delete/',
            '/api/production/health/',
            f'/api/production/health/{record.pk}/',
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
                self.assertEqual(self.client.post(path).status_code, 404)
        self.assertTrue(HealthRecord.objects.filter(pk=record.pk).exists())
        self.assertTrue(Expense.objects.filter(pk=expense.pk).exists())
