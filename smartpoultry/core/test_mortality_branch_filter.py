from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Farm, Branch
from core.forms import MortalityRecordForm
from flocks.models import Flock
from production.models import MortalityRecord


class MortalityBranchFilterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='mortality-branch-owner')
        farm = Farm.objects.create(owner=self.user, name='Farm', location='Town', established_date=date(2026, 1, 1), contact_email='owner@example.com', contact_phone='123')
        self.north = Branch.objects.create(farm=farm, name='North')
        self.south = Branch.objects.create(farm=farm, name='South')
        self.a = Flock.objects.create(user=self.user, branch=self.north, flock_id='01', breed='layers', quantity=50)
        self.b = Flock.objects.create(user=self.user, branch=self.south, flock_id='01', breed='layers', quantity=40)
        self.inactive = Flock.objects.create(user=self.user, branch=self.north, flock_id='02', breed='layers', quantity=10, status='inactive')
        self.client.force_login(self.user)

    def data(self, flock):
        return {'branch':self.north.pk, 'flock':flock.pk, 'quantity':2, 'reason':'disease', 'date':'2026-11-14'}

    def test_mismatched_branch_is_rejected_without_reducing_either_flock(self):
        response = self.client.post(reverse('mortality_record_create'), self.data(self.b))
        self.assertEqual(response.status_code, 200)
        self.assertIn('flock', response.context['form'].errors)
        self.assertFalse(MortalityRecord.objects.exists())
        self.a.refresh_from_db(); self.b.refresh_from_db()
        self.assertEqual((self.a.quantity, self.b.quantity), (50, 40))

    def test_matching_branch_reduces_only_its_flock(self):
        response = self.client.post(reverse('mortality_record_create'), self.data(self.a))
        self.assertEqual(response.status_code, 302)
        self.a.refresh_from_db(); self.b.refresh_from_db()
        self.assertEqual((self.a.quantity, self.b.quantity), (48, 40))
        self.assertEqual(MortalityRecord.objects.get().branch, self.north)

    def test_empty_branch_inactive_and_foreign_flocks_are_rejected(self):
        self.assertFalse(MortalityRecordForm({**self.data(self.a), 'branch':''}, user=self.user).is_valid())
        self.assertFalse(MortalityRecordForm(self.data(self.inactive), user=self.user).is_valid())
        other = get_user_model().objects.create_user(username='other-mortality-owner')
        foreign = Flock.objects.create(user=other, branch=self.north, flock_id='FOREIGN', breed='layers', quantity=20)
        self.assertFalse(MortalityRecordForm(self.data(foreign), user=self.user).is_valid())

    def test_edit_preserves_matching_selection_and_supplies_branch_tags(self):
        record = MortalityRecord.objects.create(user=self.user, branch=self.north, flock=self.a, quantity=2, reason='disease', date=date(2026, 11, 14))
        form = MortalityRecordForm(instance=record, user=self.user)
        html = str(form['flock'])
        self.assertIn(f'data-branch-id="{self.north.pk}"', html)
        self.assertIn(f'data-branch-id="{self.south.pk}"', html)
        self.assertNotIn('02 - layers', html)
        self.assertEqual(form['flock'].value(), self.a.pk)
