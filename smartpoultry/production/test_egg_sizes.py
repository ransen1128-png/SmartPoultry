from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError
from core.models import Farm,Branch
from core.forms import ProductionRecordForm
from flocks.models import Flock
from production.models import ProductionRecord


class EggSizeTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='egg-size-owner')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='North')
        self.flock=Flock.objects.create(user=self.user,branch=self.branch,flock_id='Layers',breed='layers',quantity=100)
        self.client.force_login(self.user)

    def payload(self,**overrides):
        return {'branch':self.branch.pk,'flock':self.flock.pk,'product_type':'eggs','egg_size':'small','quantity':'20','unit':'eggs','date':'2026-11-14',**overrides}

    def test_all_three_sizes_can_be_recorded_for_same_flock_and_day(self):
        for size in ('small','medium','large'):
            response=self.client.post(reverse('production-list'),self.payload(egg_size=size))
            self.assertEqual(response.status_code,201,response.content)
            self.assertEqual(response.data['egg_size'],size)
        duplicate=self.client.post(reverse('production-list'),self.payload())
        self.assertEqual(duplicate.status_code,400,duplicate.content)
        self.assertEqual(ProductionRecord.objects.filter(user=self.user).count(),3)

    def test_missing_invalid_and_non_egg_sizes_are_rejected(self):
        for changes in ({'egg_size':''},{'egg_size':'jumbo'},{'product_type':'meat_ready'}):
            response=self.client.post(reverse('production-list'),self.payload(**changes))
            self.assertEqual(response.status_code,400,response.content)
        self.assertFalse(ProductionRecord.objects.filter(user=self.user).exists())
        form=ProductionRecordForm(self.payload(egg_size=''),user=self.user)
        self.assertFalse(form.is_valid());self.assertIn('egg_size',form.errors)
        form=ProductionRecordForm(self.payload(egg_size='medium'),user=self.user)
        self.assertTrue(form.is_valid(),form.errors)

    def test_sale_deducts_only_selected_size_and_prevents_relabeling_sold_batch(self):
        batches={}
        for size in ('small','medium','large'):
            result=self.client.post(reverse('production-list'),self.payload(egg_size=size))
            self.assertEqual(result.status_code,201,result.content)
            batches[size]=ProductionRecord.objects.get(pk=result.data['id'])
        stock=self.client.get(reverse('revenue-available-production')).json()
        self.assertEqual({r['egg_size_label'] for r in stock},{'Small','Medium','Large'})
        sale=self.client.post(reverse('revenue-list'),{'production':batches['medium'].pk,'buyer_name':'Egg buyer','quantity':'5','price_per_unit':'10','date':'2026-11-14'})
        self.assertEqual(sale.status_code,201,sale.content)
        self.assertEqual(sale.data['egg_size_label'],'Medium')
        self.assertEqual([batches[s].available_quantity for s in ('small','medium','large')],[20,15,20])
        changed=self.client.patch(reverse('production-detail',args=[batches['medium'].pk]),{'egg_size':'small'},content_type='application/json')
        self.assertEqual(changed.status_code,400,changed.content)
        batches['medium'].egg_size='large'
        with self.assertRaises(ValidationError):batches['medium'].save()

    def test_meat_has_no_egg_size_and_existing_unknown_egg_size_is_preserved(self):
        broiler=Flock.objects.create(user=self.user,branch=self.branch,flock_id='Broilers',breed='broilers',quantity=10,placement_date=date(2026,9,1))
        response=self.client.post(reverse('production-list'),self.payload(flock=broiler.pk,product_type='meat_ready',egg_size='',quantity='2',unit='birds'))
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(response.data['egg_size'],'')
        legacy=ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=self.flock,product_type='eggs',quantity=10,unit='eggs',date=date(2026,11,1))
        changed=self.client.patch(reverse('production-detail',args=[legacy.pk]),{'quantity':'12'},content_type='application/json')
        self.assertEqual(changed.status_code,200,changed.content)
        legacy.refresh_from_db();self.assertEqual(legacy.egg_size,'')
        page=self.client.get(reverse('production_records'))
        self.assertContains(page,'Not recorded')
