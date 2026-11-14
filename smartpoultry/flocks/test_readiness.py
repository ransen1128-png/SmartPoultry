from datetime import date,timedelta
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError
from core.models import Farm,Branch
from core.forms import ProductionRecordForm
from flocks.models import Flock
from production.models import ProductionRecord
from revenue.models import Revenue
from expenses.models import Expense
from notifications.models import Notification


@patch('django.utils.timezone.localdate',return_value=date(2026,11,14))
class BroilerReadinessTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='readiness-owner')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='North')
        self.start=date(2026,8,1)
        self.flock=Flock.objects.create(user=self.user,branch=self.branch,flock_id='Broilers',breed='broilers',quantity=100,placement_date=self.start)
        self.client.force_login(self.user)

    def production(self,days):
        return {'branch':self.branch.pk,'flock':self.flock.pk,'product_type':'meat_ready','quantity':'2','unit':'birds','date':(self.start+timedelta(days=days)).isoformat()}

    def test_harvest_day_zero_and_41_rejected_without_side_effects(self,clock):
        expense_count=Expense.objects.count();notification_count=Notification.objects.count()
        for day in (0,41):
            response=self.client.post(reverse('production-list'),self.production(day))
            self.assertEqual(response.status_code,400,response.content)
            self.assertIn('42 days',str(response.data))
            form=ProductionRecordForm(self.production(day),user=self.user)
            self.assertFalse(form.is_valid())
            with self.assertRaises(ValidationError):
                ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=self.flock,product_type='meat_ready',quantity=2,unit='kg',date=self.start+timedelta(days=day))
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,100)
        self.assertFalse(ProductionRecord.objects.filter(user=self.user).exists())
        self.assertEqual(Expense.objects.count(),expense_count)
        self.assertEqual(Notification.objects.count(),notification_count)

    def test_day_42_day_60_and_later_allowed(self,clock):
        for day in (42,60,61):
            response=self.client.post(reverse('production-list'),self.production(day))
            self.assertEqual(response.status_code,201,response.content)
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,94)

    def test_sale_cannot_bypass_readiness_using_old_production(self,clock):
        ProductionRecord.objects.bulk_create([ProductionRecord(user=self.user,branch=self.branch,flock=self.flock,product_type='meat_ready',quantity=10,unit='birds',date=self.start)])
        batch=ProductionRecord.objects.get(user=self.user)
        with self.assertRaises(ValidationError):batch.apply_bird_transfer(self.user)
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,100)
        for day in (0,41,200):
            response=self.client.post(reverse('revenue-list'),{'production':batch.pk,'quantity':'2','price_per_unit':'100','date':(self.start+timedelta(days=day)).isoformat(),'buyer_name':'Buyer'})
            self.assertEqual(response.status_code,400,response.content)
        self.assertEqual(batch.available_quantity,10)
        self.assertFalse(Revenue.objects.filter(user=self.user).exists())
        response=self.client.post(reverse('revenue-list'),{'production':batch.pk,'quantity':'2','price_per_unit':'100','date':(self.start+timedelta(days=42)).isoformat(),'buyer_name':'Buyer'})
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(batch.available_quantity,8)

    def test_missing_delivery_date_blocks_new_harvest_but_preserves_legacy_notes(self,clock):
        self.flock.placement_date=None;self.flock.save()
        result=self.client.post(reverse('production-list'),self.production(60))
        self.assertEqual(result.status_code,400,result.content)
        self.assertIn('delivery / hatch date',str(result.data))
        ProductionRecord.objects.bulk_create([ProductionRecord(user=self.user,branch=self.branch,flock=self.flock,product_type='meat_ready',quantity=10,unit='kg',date=self.start)])
        batch=ProductionRecord.objects.get(user=self.user);batch.notes='Preserve the historical record';batch.save()
        self.assertEqual(self.client.get(reverse('revenue-available-production')).json(),[])

    def test_future_harvest_is_rejected_and_immature_stock_hidden(self,clock):
        self.flock.placement_date=date(2026,11,14);self.flock.save()
        result=self.client.post(reverse('production-list'),self.production(147))
        self.assertEqual(result.status_code,400,result.content)
        self.assertIn('advance',str(result.data))
        ProductionRecord.objects.bulk_create([ProductionRecord(user=self.user,branch=self.branch,flock=self.flock,product_type='meat_ready',quantity=10,unit='birds',date=date(2026,11,14))])
        self.assertEqual(self.client.get(reverse('revenue-available-production')).json(),[])

    def test_new_broiler_requires_actual_placement_date(self,clock):
        payload={'branch':self.branch.pk,'flock_id':'New','breed':'broilers','quantity':10,'acquisition_source':'own'}
        for placement in (None,'2026-11-15'):
            result=self.client.post(reverse('flock-list'),payload if placement is None else {**payload,'placement_date':placement})
            self.assertEqual(result.status_code,400,result.content)
        result=self.client.post(reverse('flock-list'),{**payload,'placement_date':'2026-11-14'})
        self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(result.data['ready_from'],'2026-12-26')
        self.assertEqual(result.data['readiness_window_end'],'2027-01-13')
