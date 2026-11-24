from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import AuditEvent, Branch, Farm
from flocks.models import Flock
from notifications.models import Notification, NotificationPreference
from production.models import HealthRecord


class HealthRecordPageTests(TestCase):
    def account(self, name):
        user = get_user_model().objects.create_user(name, email=f'{name}@example.com', password='Secret!123')
        farm = Farm.objects.create(owner=user, name=f'{name} Farm', location='Argao', established_date='2026-01-01',
                                   contact_email=user.email, contact_phone='09170000000')
        branch = Branch.objects.create(farm=farm, name=f'{name} Branch')
        return user, branch, Flock.objects.create(user=user, branch=branch, flock_id='01', breed='layers', quantity=10)

    def setUp(self):
        self.user, self.branch, self.flock = self.account('alpha')
        self.other, _, self.other_flock = self.account('beta')
        self.client.force_login(self.user)

    def data(self, **changes):
        return {'flock': self.flock.pk, 'date': '2026-01-10', 'health_status': 'treated', 'vaccination_name': 'NDV',
                'disease_name': '', 'medication': 'Vitamins', 'treatment': '', 'notes': '', **changes}

    def test_login_is_required(self):
        self.client.logout()
        for name in ('health_records', 'health_record_create'):
            self.assertIn('/login/', self.client.get(reverse(name))['Location'])

    def test_create_list_edit_delete_and_change_history(self):
        self.assertRedirects(self.client.post(reverse('health_record_create'), self.data()), reverse('health_records'))
        record = HealthRecord.objects.get()
        self.assertEqual(record.flock, self.flock)
        page = self.client.get(reverse('health_records'))
        self.assertContains(page, 'NDV')
        self.assertContains(page, 'alpha Branch')
        self.client.post(reverse('health_record_update', args=[record.pk]),
                         self.data(health_status='recovered', correction_reason='Recovered after review'))
        event = AuditEvent.objects.get(object_type='production.HealthRecord', object_id=record.pk, action='updated')
        self.assertEqual((event.owner, event.before['health_status'], event.after['health_status'], event.reason),
                         (self.user, 'treated', 'recovered', 'Recovered after review'))
        self.client.get(reverse('health_record_delete', args=[record.pk]))
        self.assertTrue(HealthRecord.objects.filter(pk=record.pk).exists())
        self.client.post(reverse('health_record_delete', args=[record.pk]))
        self.assertFalse(HealthRecord.objects.exists())
        self.assertTrue(AuditEvent.objects.filter(object_type='production.HealthRecord', action='deleted').exists())

    def test_other_accounts_are_isolated(self):
        theirs = HealthRecord.objects.create(flock=self.other_flock, date=date(2026, 1, 1), vaccination_name='PrivateVaccine')
        self.assertNotContains(self.client.get(reverse('health_records')), 'PrivateVaccine')
        self.assertNotContains(self.client.get(reverse('health_record_create')), 'beta Branch')
        for name in ('health_record_update', 'health_record_delete'):
            self.assertEqual(self.client.post(reverse(name, args=[theirs.pk]), self.data()).status_code, 404)
        self.client.post(reverse('health_record_create'), self.data(flock=self.other_flock.pk))
        self.assertEqual(HealthRecord.objects.count(), 1)

    def test_future_dates_and_empty_details_are_rejected(self):
        future = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertContains(self.client.post(reverse('health_record_create'), self.data(date=future)), 'cannot be in the future')
        response = self.client.post(reverse('health_record_create'),
                                    self.data(vaccination_name='', medication='', health_status='sick'))
        self.assertContains(response, 'Enter the disease, treatment')
        self.assertFalse(HealthRecord.objects.exists())

    def test_same_flock_id_in_two_branches_shows_the_branch(self):
        second = Branch.objects.create(farm=self.branch.farm, name='Second Branch')
        Flock.objects.create(user=self.user, branch=second, flock_id='01', breed='layers', quantity=5)
        page = self.client.get(reverse('health_record_create'))
        self.assertContains(page, '01 (alpha Branch)')
        self.assertContains(page, '01 (Second Branch)')

    def test_main_branch_flock_can_be_recorded(self):
        flock = Flock.objects.create(user=self.user, flock_id='01', breed='layers', quantity=5)
        self.client.post(reverse('health_record_create'), self.data(flock=flock.pk))
        self.assertContains(self.client.get(reverse('health_records')), 'Main Branch')

    def test_record_of_a_sold_flock_can_still_be_corrected(self):
        record = HealthRecord.objects.create(flock=self.flock, date=date(2026, 1, 1), vaccination_name='NDV')
        Flock.objects.filter(pk=self.flock.pk).update(status='sold')
        self.client.post(reverse('health_record_update', args=[record.pk]), self.data(vaccination_name='IBD', correction_reason='Typo'))
        record.refresh_from_db()
        self.assertEqual(record.vaccination_name, 'IBD')

    def test_notification_follows_the_in_app_setting(self):
        NotificationPreference.objects.update_or_create(user=self.user, defaults={'in_app_notifications': False})
        self.client.post(reverse('health_record_create'), self.data())
        self.assertFalse(Notification.objects.filter(user=self.user).exists())

    def test_deleting_the_account_still_works(self):
        HealthRecord.objects.create(flock=self.flock, date=date(2026, 1, 1))
        self.user.delete()
        self.assertFalse(HealthRecord.objects.exists())
