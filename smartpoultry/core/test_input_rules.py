import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Branch, Farm, Feedback
from expenses.models import Expense
from flocks.models import Flock
from inventory.models import FeedType, Inventory
from notifications.models import NotificationPreference
from production.models import BreedInformation, MortalityRecord, ProductionRecord


class InputRuleTests(TestCase):
    """Values that used to end in a server error or store an impossible record."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('rules-owner', email='rules@example.com', password='x')
        farm = Farm.objects.create(owner=self.user, name='Farm', location='Town', established_date=date(2026, 1, 1),
                                   contact_email='a@example.com', contact_phone='09170000000')
        self.branch = Branch.objects.create(farm=farm, name='North')
        self.flock = Flock.objects.create(user=self.user, branch=self.branch, flock_id='01', breed='layers', quantity=50)
        self.batch = ProductionRecord.objects.create(user=self.user, branch=self.branch, flock=self.flock, product_type='eggs',
                                                     egg_size='medium', quantity=100, unit='units', date=date(2026, 11, 1))
        self.client.force_login(self.user)

    def send(self, path, data, method='post'):
        return getattr(self.client, method)(path, json.dumps(data), content_type='application/json')

    def payloads(self, day):
        day = day.isoformat()
        stock = Inventory.objects.create(user=self.user, name='Feed', item_type='feed', quantity=20, unit='kg', cost_per_unit=5)
        base = {'branch': self.branch.pk, 'flock': self.flock.pk, 'quantity': 1, 'date': day}
        return {
            reverse('expense-list'): {'branch': self.branch.pk, 'expense_type': 'feed', 'description': 'x', 'amount': 1, 'date': day},
            reverse('production-list'): {**base, 'product_type': 'eggs', 'egg_size': 'small'},
            '/api/production/mortality/': {**base, 'reason': 'disease'},
            reverse('revenue-list'): {'production': self.batch.pk, 'quantity': 1, 'price_per_unit': 1, 'date': day, 'buyer_name': 'x'},
            '/api/inventory/distributions/': {**base, 'inventory': stock.pk},
        }

    def test_records_cannot_be_dated_in_the_future_or_before_2000(self):
        for day in (timezone.localdate() + timedelta(days=1), date(1999, 12, 31)):
            for path, data in self.payloads(day).items():
                response = self.send(path, data)
                self.assertEqual((path, response.status_code), (path, 400), response.content)
                self.assertIn('date', response.json())
        self.flock.refresh_from_db()
        self.assertEqual(self.flock.quantity, 50)
        self.assertFalse(Expense.objects.filter(description='x').exists() or MortalityRecord.objects.exists())

    def test_records_dated_today_are_saved(self):
        for path, data in self.payloads(timezone.localdate()).items():
            response = self.send(path, data)
            self.assertEqual((path, response.status_code), (path, 201), response.content)

    def test_pages_also_reject_future_dates(self):
        day = (timezone.localdate() + timedelta(days=1)).isoformat()
        base = {'branch': self.branch.pk, 'flock': self.flock.pk, 'quantity': 1, 'date': day}
        for path, extra in (('/production-records/add/', {'product_type': 'eggs', 'egg_size': 'small', 'unit': 'units'}),
                            ('/mortality-records/add/', {'reason': 'disease'})):
            self.assertContains(self.client.post(path, {**base, **extra}), 'cannot be in the future')

    def test_an_older_record_with_a_future_date_can_still_be_corrected(self):
        row = Expense.objects.create(user=self.user, branch=self.branch, expense_type='feed', description='Old', amount=1,
                                     date=timezone.localdate() + timedelta(days=30))
        path = reverse('expense-detail', args=[row.pk])
        same = {'description': 'Corrected', 'date': row.date.isoformat(), 'correction_reason': 'Typing error'}
        self.assertEqual(self.send(path, same, 'patch').status_code, 200)
        later = {**same, 'date': (row.date + timedelta(days=1)).isoformat()}
        self.assertEqual(self.send(path, later, 'patch').status_code, 400)

    def test_flock_purchase_date_cannot_be_in_the_future(self):
        response = self.send('/api/flocks/', {'branch': self.branch.pk, 'breed': 'layers', 'quantity': 5, 'acquisition_source': 'purchased',
                             'purchase_amount': 10, 'purchase_date': (timezone.localdate() + timedelta(days=1)).isoformat()})
        self.assertEqual(response.status_code, 400)
        self.assertIn('purchase_date', response.json())

    def test_unusual_ids_are_not_server_errors(self):
        for value in ('²', '٣', '9' * 40, 'abc'):
            for path in ('/dashboard/?branch=', '/forecasting/?branch=', '/rooster-age-estimator/?estimate=',
                         '/api/inventory/distributions/?inventory=', '/api/reports/branch-expenses/?branch='):
                self.assertLess(self.client.get(path + value).status_code, 500, (path, value))
            self.assertEqual(self.client.post('/change-history/', {'event': value, 'reason': 'x'}).status_code, 404)
            self.assertLess(self.client.post('/farm/branches/', {'action': 'save', 'branch_id': value}).status_code, 500)
            if len(value) < 20:  # SQLite alone cannot compare larger numbers.
                self.assertLess(self.client.post('/production-records/add/', {'branch': value}).status_code, 500)

    def test_characters_that_cannot_be_saved_are_refused(self):
        self.assertEqual(self.client.get('/change-history/?type=a%00b').status_code, 400)
        self.assertEqual(self.client.post('/feedback/', {'subject': 'a\x00', 'message': 'x'}).status_code, 400)
        response = self.send(reverse('expense-list'), {**self.payloads(timezone.localdate())[reverse('expense-list')], 'correction_reason': 'a\x00'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Feedback.objects.exists() or Expense.objects.filter(description='x').exists())

    def test_long_feedback_subject_is_explained(self):
        self.assertContains(self.client.post('/feedback/', {'subject': 'x' * 256, 'message': 'x'}), 'at most 255 characters')
        self.assertFalse(Feedback.objects.exists())

    def test_long_or_invalid_profile_values_are_explained(self):
        good = {'username': 'rules-owner', 'email': 'rules@example.com', 'first_name': 'A', 'last_name': 'B', 'phone': ''}
        for name, value in (('username', 'x' * 151), ('first_name', 'x' * 151), ('last_name', 'x' * 151),
                            ('email', 'a@' + 'x' * 260 + '.com'), ('email', 'not-an-email')):
            response = self.client.post('/profile/', {**good, name: value})
            self.assertEqual(response.status_code, 200, name)
            self.assertTrue(list(response.context['messages']), name)
        self.user.refresh_from_db()
        self.assertEqual((self.user.username, self.user.email, self.user.first_name), ('rules-owner', 'rules@example.com', ''))

    def test_profile_keeps_an_older_username_that_is_not_being_changed(self):
        get_user_model().objects.filter(pk=self.user.pk).update(username='Old Name')
        response = self.client.post('/profile/', {'username': 'Old Name', 'email': 'rules@example.com', 'first_name': 'New'})
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'New')

    def test_saving_preferences_twice_updates_them(self):
        for value in (True, False):
            self.assertEqual(self.send('/api/notifications/preferences/', {'in_app_notifications': value}).status_code, 201)
        self.assertEqual(NotificationPreference.objects.filter(user=self.user).count(), 1)
        self.assertFalse(NotificationPreference.objects.get(user=self.user).in_app_notifications)

    def test_report_end_cannot_precede_start(self):
        data = {'report_type': 'monthly', 'title': 'x', 'start_date': '2026-11-30', 'end_date': '2026-11-01'}
        self.assertIn('end_date', self.send('/api/reports/', data).json())


class SimultaneousRequestTests(TestCase):
    """What the second of two simultaneous requests gets."""

    def setUp(self):
        InputRuleTests.setUp(self)

    def test_deleting_the_same_mortality_record_twice_restores_the_chicken_once(self):
        record = MortalityRecord.objects.create(user=self.user, branch=self.branch, flock=self.flock, quantity=5, reason='disease', date=date(2026, 11, 2))
        first, second = (MortalityRecord.objects.get(pk=record.pk) for _ in range(2))
        first.delete()
        second.delete()
        self.flock.refresh_from_db()
        self.assertEqual(self.flock.quantity, 50)

    def test_deleting_the_same_production_record_twice_is_harmless(self):
        first, second = (ProductionRecord.objects.get(pk=self.batch.pk) for _ in range(2))
        first.delete()
        self.assertEqual(second.delete()[0], 0)

    def test_a_rule_refused_while_saving_is_a_message_not_a_server_error(self):
        error = ValidationError({'quantity': 'Only 10 left.'})
        data = {'branch': self.branch.pk, 'flock': self.flock.pk, 'quantity': 1, 'reason': 'disease', 'date': '2026-11-03'}
        with patch.object(MortalityRecord, 'save', side_effect=error):
            response = self.client.post('/api/production/mortality/', json.dumps(data), content_type='application/json')
            self.assertEqual((response.status_code, response.json()), (400, {'quantity': ['Only 10 left.']}))
            self.assertContains(self.client.post('/mortality-records/add/', data), 'Only 10 left.')


class SharedDataPermissionTests(TestCase):
    """Breeds and feed types are shared by every farm; administrator accounts belong to the superuser."""

    def setUp(self):
        create = get_user_model().objects.create_user
        self.owner, self.staff = create('shared-owner', email='o@example.com'), create('staff-a', email='a@example.com', is_staff=True)
        self.other = create('staff-b', email='b@example.com', is_staff=True)
        self.chief = get_user_model().objects.create_superuser('chief', email='c@example.com', password='x')
        fields = {field.name for field in BreedInformation._meta.fields}
        values = {'name': 'Shared', 'type': 'layers', 'egg_production_per_year': 1, 'growth_period_days': 1, 'average_weight_kg': 1,
                  'feed_consumption_daily_kg': 1, 'lifespan_years': 1, 'characteristics': 'x'}
        self.breed = BreedInformation.objects.create(**{name: value for name, value in values.items() if name in fields})
        self.feed = FeedType.objects.create(name='Shared', unit='kg', cost_per_unit=1)

    def call(self, user, method, path, data=None):
        self.client.force_login(user)
        return getattr(self.client, method)(path, json.dumps(data or {}), content_type='application/json').status_code

    def test_owners_read_but_do_not_change_shared_lists(self):
        for base, row in (('/api/production/breeds/', self.breed), ('/api/inventory/feed-types/', self.feed)):
            path = f'{base}{row.pk}/'
            self.client.force_login(self.owner)
            self.assertEqual([self.client.get(base).status_code, self.client.get(path).status_code], [200, 200])
            calls = (('post', base, {'name': 'N'}), ('patch', path, {'name': 'N'}), ('put', path, {'name': 'N'}), ('delete', path))
            self.assertEqual([self.call(self.owner, *call) for call in calls], [403] * 4)
            self.assertEqual(self.call(self.staff, 'patch', path, {'name': 'Renamed'}), 200)

    def test_staff_cannot_change_or_delete_other_administrators_through_the_api(self):
        for target in (self.other, self.chief):
            path = f'/api/accounts/users/{target.pk}/'
            self.assertEqual([self.call(self.staff, 'patch', path, {'email': 'taken@example.com'}), self.call(self.staff, 'delete', path)], [403, 403])
            target.refresh_from_db()
            self.assertNotEqual(target.email, 'taken@example.com')

    def test_staff_still_manage_owners_and_their_own_details(self):
        self.assertEqual(self.call(self.staff, 'patch', f'/api/accounts/users/{self.staff.pk}/', {'first_name': 'Me'}), 200)
        self.assertEqual(self.call(self.staff, 'patch', f'/api/accounts/users/{self.owner.pk}/', {'first_name': 'Own'}), 200)
        self.assertEqual(self.call(self.staff, 'delete', f'/api/accounts/users/{self.owner.pk}/'), 204)

    def test_superuser_manages_administrators_through_the_api(self):
        path = f'/api/accounts/users/{self.other.pk}/'
        self.assertEqual([self.call(self.chief, 'patch', path, {'first_name': 'X'}), self.call(self.chief, 'delete', path)], [200, 204])
