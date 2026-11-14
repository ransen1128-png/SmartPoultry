from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Farm,Branch
from flocks.models import Flock
from production.models import ProductionRecord
from revenue.models import Revenue


class ProductionHistoryTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='production-history-owner')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='North')
        self.flock=Flock.objects.create(user=self.user,branch=self.branch,flock_id='Layers',breed='layers',quantity=20)
        self.batch=ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=self.flock,product_type='eggs',egg_size='medium',quantity=20,unit='pcs',date=date(2026,11,1))
        self.client.force_login(self.user)

    def sale(self,batch,quantity):
        return self.client.post(reverse('revenue-list'),{'production':batch.pk,'buyer_name':'Buyer','quantity':str(quantity),'price_per_unit':'7','date':'2026-11-02'})

    def ids(self,response,key):
        return {row.pk for row in response.context[key]}

    def test_unsold_and_partially_sold_stay_current_until_last_sale(self):
        page=self.client.get(reverse('production_records'))
        self.assertEqual(self.ids(page,'records'),{self.batch.pk})
        self.assertEqual(self.ids(page,'production_history'),set())
        first=self.sale(self.batch,5);self.assertEqual(first.status_code,201,first.content)
        page=self.client.get(reverse('production_records'))
        self.assertEqual(self.ids(page,'records'),{self.batch.pk})
        self.assertEqual(page.context['records'][0].available_quantity,15)
        last=self.sale(self.batch,15);self.assertEqual(last.status_code,201,last.content)
        page=self.client.get(reverse('production_records'))
        self.assertEqual(self.ids(page,'records'),set())
        self.assertEqual(self.ids(page,'production_history'),{self.batch.pk})
        self.assertEqual(len(page.context['sales_history']),2)
        self.assertEqual(ProductionRecord.objects.filter(user=self.user).count(),1)
        self.assertEqual(Revenue.objects.filter(user=self.user).count(),2)
        self.assertContains(page,'No production stock available.')

    def test_sale_correction_and_deletion_restore_batch_to_current(self):
        result=self.sale(self.batch,20);self.assertEqual(result.status_code,201,result.content)
        detail=reverse('revenue-detail',args=[result.data['id']])
        changed=self.client.patch(detail,{'quantity':'19'},content_type='application/json')
        self.assertEqual(changed.status_code,200,changed.content)
        page=self.client.get(reverse('production_records'))
        self.assertEqual(self.ids(page,'records'),{self.batch.pk})
        self.assertEqual(self.ids(page,'production_history'),set())
        self.assertEqual(page.context['records'][0].available_quantity,1)
        self.assertEqual(self.client.patch(detail,{'quantity':'20'},content_type='application/json').status_code,200)
        self.assertEqual(self.client.delete(detail).status_code,204)
        page=self.client.get(reverse('production_records'))
        self.assertEqual(self.ids(page,'records'),{self.batch.pk})
        self.assertEqual(page.context['records'][0].available_quantity,20)

    def test_fully_sold_meat_remains_in_history_after_flock_auto_sold(self):
        flock=Flock.objects.create(user=self.user,branch=self.branch,flock_id='Broilers',breed='broilers',quantity=10,placement_date=date(2026,8,1))
        batch=ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=flock,product_type='meat_ready',quantity=10,unit='chicken',date=date(2026,11,1))
        result=self.sale(batch,10);self.assertEqual(result.status_code,201,result.content)
        flock.refresh_from_db();self.assertEqual((flock.quantity,flock.status),(0,'sold'))
        page=self.client.get(reverse('production_records'))
        self.assertNotIn(batch.pk,self.ids(page,'records'))
        self.assertIn(batch.pk,self.ids(page,'production_history'))
        self.assertEqual(batch.available_quantity,0)

    def test_history_is_owner_scoped_and_inactive_records_remain_hidden(self):
        result=self.sale(self.batch,20);self.assertEqual(result.status_code,201,result.content)
        other=get_user_model().objects.create_user(username='production-history-outsider')
        self.client.force_login(other)
        page=self.client.get(reverse('production_records'))
        self.assertEqual(self.ids(page,'records'),set());self.assertEqual(self.ids(page,'production_history'),set())
        self.client.force_login(self.user)
        self.flock.status='inactive';self.flock.save()
        page=self.client.get(reverse('production_records'))
        self.assertEqual(self.ids(page,'production_history'),set())
        self.flock.status='active';self.flock.save()
        self.assertIn(self.batch.pk,self.ids(self.client.get(reverse('production_records')),'production_history'))
