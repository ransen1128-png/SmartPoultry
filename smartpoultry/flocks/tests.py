from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError
from core.models import Farm,Branch
from flocks.models import Flock
from production.models import ProductionRecord,MortalityRecord
from revenue.models import Revenue


class BroilerHistoryTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='broiler-history-owner')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='Main')
        self.flock=Flock.objects.create(user=self.user,branch=self.branch,flock_id='BROILER-1',breed='broilers',quantity=20,placement_date=date(2026,9,1))
        self.client.force_login(self.user)

    def produce(self,quantity=20,unit='units',day=14):
        return ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=self.flock,product_type='meat_ready',quantity=Decimal(str(quantity)),unit=unit,date=date(2026,11,day))

    def sell(self,production,quantity):
        return self.client.post(reverse('revenue-list'),{'buyer_name':'Test buyer','production':production.pk,'quantity':quantity,'price_per_unit':'100','date':'2026-11-14'})

    def test_full_production_moves_flock_to_history_but_stock_can_be_sold(self):
        production=self.produce()
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,0)
        self.assertTrue(self.flock.in_history);self.assertEqual(self.flock.status,'active')
        dashboard=self.client.get(reverse('dashboard'),{'month':11,'year':2026})
        self.assertEqual(dashboard.context['metrics']['active_flocks'],0)
        self.assertEqual(self.client.get(reverse('revenue-available-production')).json()[0]['id'],production.pk)
        self.assertEqual(self.sell(production,20).status_code,201)
        self.flock.refresh_from_db()
        self.assertEqual((self.flock.quantity,self.flock.status,self.flock.auto_sold),(0,'sold',True))
        self.assertEqual(self.client.get(reverse('revenue-available-production')).json(),[])
        self.assertTrue(self.client.get(reverse('flock-detail',args=[self.flock.pk])).json()['in_history'])

    def test_partial_production_and_sales_do_not_remove_birds_twice(self):
        first=self.produce(5,day=13)
        self.assertEqual(self.sell(first,5).status_code,201)
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,15)
        self.assertFalse(self.flock.in_history)
        second=self.produce(15)
        self.assertEqual(self.sell(second,10).status_code,201)
        self.flock.refresh_from_db();self.assertEqual((self.flock.quantity,self.flock.status),(0,'active'))
        self.assertEqual(self.sell(second,5).status_code,201)
        self.flock.refresh_from_db();self.assertEqual(self.flock.status,'sold')

    def test_sale_correction_reopens_stock_without_restoring_live_birds(self):
        production=self.produce();self.sell(production,20)
        sale=Revenue.objects.get()
        result=self.client.patch(reverse('revenue-detail',args=[sale.pk]),{'quantity':'15'},content_type='application/json')
        self.assertEqual(result.status_code,200,result.content)
        self.flock.refresh_from_db();self.assertEqual((self.flock.quantity,self.flock.status),(0,'active'))
        self.assertEqual(production.available_quantity,5)
        self.assertEqual(self.client.delete(reverse('revenue-detail',args=[sale.pk])).status_code,204)
        self.assertEqual(production.available_quantity,20)
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,0)

    def test_editing_or_deleting_unsold_production_restores_live_count(self):
        production=self.produce(10)
        production.quantity=Decimal('8');production.save()
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,12)
        production.delete()
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,20)
        self.assertFalse(self.flock.in_history)

    def test_overproduction_and_fractional_bird_counts_are_rejected(self):
        for quantity in (21,Decimal('1.5')):
            with self.assertRaises(ValidationError):self.produce(quantity)
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,20)
        self.assertFalse(ProductionRecord.objects.exists())
        result=self.client.post(reverse('production-list'),{'branch':self.branch.pk,'flock':self.flock.pk,'product_type':'meat_ready','quantity':'21','date':'2026-11-14'})
        self.assertEqual(result.status_code,400,result.content)

    def test_stale_flock_object_cannot_overallocate_a_second_production_batch(self):
        self.produce(15,day=13)
        with self.assertRaises(ValidationError):self.produce(10)
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,5)
        self.assertEqual(ProductionRecord.objects.count(),1)

    def test_weight_is_not_converted_into_a_guessed_bird_count(self):
        production=self.produce(40,unit='kg')
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,20)
        self.assertEqual(production.birds_removed,0)

    def test_zero_mortality_and_manually_sold_flocks_are_in_history(self):
        MortalityRecord.objects.create(user=self.user,branch=self.branch,flock=self.flock,quantity=20,reason='disease',date=date(2026,11,14))
        self.flock.refresh_from_db();self.assertTrue(self.flock.in_history)
        self.flock.quantity=10;self.flock.status='sold';self.flock.save()
        self.assertTrue(self.flock.in_history)

    def test_activity_history_is_not_deleted_or_visible_to_another_owner(self):
        self.produce()
        self.assertEqual(self.client.delete(reverse('flock-detail',args=[self.flock.pk])).status_code,400)
        other=get_user_model().objects.create_user(username='broiler-history-other')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('flock-detail',args=[self.flock.pk])).status_code,404)

    def test_zero_flock_is_retained_even_without_other_records(self):
        self.flock.quantity=0;self.flock.save()
        self.assertEqual(self.client.delete(reverse('flock-detail',args=[self.flock.pk])).status_code,400)
        self.assertTrue(Flock.objects.filter(pk=self.flock.pk).exists())

    def test_historical_production_is_not_silently_recounted(self):
        ProductionRecord.objects.bulk_create([ProductionRecord(user=self.user,branch=self.branch,flock=self.flock,product_type='meat_ready',quantity=30,unit='units',date=date(2026,11,13))])
        production=ProductionRecord.objects.get();production.notes='Historical review';production.save()
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,20)
        self.assertEqual(production.birds_removed,0)

    def test_legacy_bird_count_requires_confirmation_and_is_applied_only_once(self):
        ProductionRecord.objects.bulk_create([ProductionRecord(user=self.user,branch=self.branch,flock=self.flock,product_type='meat_ready',quantity=20,unit='units',date=date(2026,11,13))])
        production=ProductionRecord.objects.get();url=reverse('production_apply_birds',args=[production.pk])
        self.assertEqual(self.client.post(url,{}).status_code,200)
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,20)
        for _ in range(2):self.assertEqual(self.client.post(url,{'confirmed':'yes'}).status_code,302)
        self.flock.refresh_from_db();self.assertEqual(self.flock.quantity,0)
        self.assertTrue(self.flock.in_history)
        production.refresh_from_db();self.assertEqual(production.birds_removed,20)
        self.assertIn('confirmed by account',production.notes)
