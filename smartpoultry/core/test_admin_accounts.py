import csv
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdministratorAccountTests(TestCase):
    """AD-12 to AD-14: exporting users, administrator levels and the user list."""

    def setUp(self):
        create = get_user_model().objects.create_user
        self.staff = create('staff-one', email='staff1@example.com', is_staff=True)
        self.other = create('staff-two', email='staff2@example.com', is_staff=True)
        self.owner = create('farm-owner', email='owner@example.com', phone='=1+1')
        self.superuser = get_user_model().objects.create_superuser('chief', email='chief@example.com', password='x')

    def toggle(self, target, action='deactivate'):
        self.client.post(reverse('admin_toggle_user', args=[target.pk]), {'action': action})
        target.refresh_from_db()
        return target.is_active and target.is_active_user

    def deleted(self, target):
        self.client.post(reverse('admin_delete_user', args=[target.pk]))
        return not get_user_model().objects.filter(pk=target.pk).exists()

    def test_staff_cannot_disable_or_delete_administrators(self):
        self.client.force_login(self.staff)
        for target in (self.superuser, self.other):
            self.assertTrue(self.toggle(target))
            self.assertFalse(self.deleted(target))

    def test_staff_cannot_reactivate_an_administrator(self):
        get_user_model().objects.filter(pk=self.other.pk).update(is_active=False, is_active_user=False)
        self.client.force_login(self.staff)
        self.assertFalse(self.toggle(self.other, 'activate'))

    def test_staff_still_manage_owners(self):
        self.client.force_login(self.staff)
        self.assertFalse(self.toggle(self.owner))
        self.assertTrue(self.toggle(self.owner, 'activate'))
        self.assertTrue(self.deleted(self.owner))

    def test_superuser_manages_staff_but_not_self(self):
        self.client.force_login(self.superuser)
        self.assertFalse(self.toggle(self.other))
        self.assertTrue(self.deleted(self.other))
        self.assertTrue(self.toggle(self.superuser))
        self.assertFalse(self.deleted(self.superuser))

    def test_buttons_for_administrators_are_off_for_staff_only(self):
        disabled = {}
        for user in (self.staff, self.superuser):
            self.client.force_login(user)
            disabled[user.username] = self.client.get(reverse('admin_dashboard')).content.decode().count('Only a superuser can')
        # Three administrator rows, two buttons each.
        self.assertEqual(disabled, {'staff-one': 6, 'chief': 0})

    def rows(self, **params):
        response = self.client.get(reverse('admin_export_users'), params)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        return list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))

    def test_export_is_a_csv_of_the_listed_users(self):
        self.client.force_login(self.staff)
        rows = self.rows()
        self.assertEqual({row['Username'] for row in rows}, {'staff-one', 'staff-two', 'farm-owner', 'chief'})
        self.assertEqual([row['Username'] for row in self.rows(q='farm-owner')], ['farm-owner'])
        self.assertEqual(self.rows(status='inactive'), [])
        owner = next(row for row in rows if row['Username'] == 'farm-owner')
        self.assertEqual((owner['Role'], owner['Status'], owner['Phone']), ('Poultry Farm Owner', 'Active', "'=1+1"))
        self.assertFalse(any('password' in key.lower() for key in owner))

    def test_export_is_for_administrators_only(self):
        self.assertIn('/login/', self.client.get(reverse('admin_export_users'))['Location'])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('admin_export_users')).status_code, 403)

    def test_list_has_no_page_buttons_that_do_nothing(self):
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(reverse('admin_dashboard')), 'admin-pagination')
