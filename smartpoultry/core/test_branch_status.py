from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Farm, Branch
from core.forms import ProductionRecordForm, MortalityRecordForm
from flocks.models import Flock
from production.models import ProductionRecord, MortalityRecord


class BranchStatusTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='branch-status-owner', password='password123')
        farm = Farm.objects.create(owner=self.user, name='Farm', location='Test', established_date=date(2026,1,1), contact_email='test@example.com', contact_phone='123')
        self.branch = Branch.objects.create(farm=farm, name='Main')
        self.flock = Flock.objects.create(user=self.user, branch=self.branch, flock_id='LAYER-1', breed='layers', quantity=20)
        ProductionRecord.objects.create(user=self.user, branch=self.branch, flock=self.flock, product_type='eggs', quantity=5, date=date(2026,11,12))
        MortalityRecord.objects.create(user=self.user, branch=self.branch, flock=self.flock, quantity=1, date=date(2026,11,12))
        self.client.force_login(self.user)

    def test_flock_deactivation_hides_and_reactivation_restores_records(self):
        for status, count in [('inactive',0), ('active',1)]:
            response = self.client.patch(reverse('flock-detail',args=[self.flock.pk]), data={'status':status}, content_type='application/json')
            self.assertEqual(response.status_code,200)
            for url in ('production_records','mortality_records'):
                self.assertEqual(len(self.client.get(reverse(url)).context['records']),count)
            for url in ('production-list','mortality-list'):
                self.assertEqual(self.client.get(reverse(url)).json()['count'],count)
        self.assertEqual(ProductionRecord.objects.count(),1)
        self.assertEqual(MortalityRecord.objects.count(),1)

    def test_branch_edit_modal_and_deactivation_cascade(self):
        self.assertContains(self.client.get(reverse('farm_branches')),f'id="editBranch{self.branch.pk}"')
        response=self.client.post(reverse('farm_branches'),{'branch_id':self.branch.pk,'branch_name':'Renamed','status':'inactive'})
        self.assertEqual(response.status_code,302)
        self.flock.refresh_from_db()
        self.assertEqual(self.flock.status,'inactive')
        self.assertEqual(self.flock.quantity,19)
        for form in (ProductionRecordForm(user=self.user),MortalityRecordForm(user=self.user)):
            self.assertFalse(form.fields['flock'].queryset.filter(pk=self.flock.pk).exists())
            self.assertFalse(form.fields['branch'].queryset.filter(pk=self.branch.pk).exists())
        response=self.client.patch(reverse('flock-detail',args=[self.flock.pk]),data={'status':'active'},content_type='application/json')
        self.assertEqual(response.status_code,400)

    def test_layers_only_branch_rejects_meat_and_inactive_record_submission(self):
        form=ProductionRecordForm(data={'branch':self.branch.pk,'flock':self.flock.pk,'product_type':'meat_ready','quantity':2,'date':'2026-11-13'},user=self.user)
        self.assertEqual(list(form.fields['product_type'].choices),[('eggs','Eggs')])
        self.assertFalse(form.is_valid())
        self.flock.status='inactive';self.flock.save()
        for url,payload in [('production-list',{'product_type':'eggs','quantity':2}),('mortality-list',{'quantity':1})]:
            response=self.client.post(reverse(url),{'branch':self.branch.pk,'flock':self.flock.pk,'date':'2026-11-13',**payload})
            self.assertEqual(response.status_code,400)

    def test_other_account_cannot_edit_branch(self):
        other=get_user_model().objects.create_user(username='branch-status-other',password='password123')
        self.client.force_login(other)
        # No farm profile: a forged branch edit must not change the owned branch.
        self.client.post(reverse('farm_branches'),{'branch_id':self.branch.pk,'branch_name':'Stolen','status':'inactive'})
        self.branch.refresh_from_db();self.assertEqual(self.branch.name,'Main')
