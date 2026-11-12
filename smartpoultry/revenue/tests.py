from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Farm, Branch
from flocks.models import Flock
from production.models import ProductionRecord
from revenue.models import Revenue


class ProductionSalesTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='production-sales',password='password123')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Test',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='Main')
        self.flock=Flock.objects.create(user=self.user,branch=self.branch,flock_id='EGG-1',breed='layers',quantity=50)
        self.production=ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=self.flock,product_type='eggs',quantity=100,unit='eggs',date=date(2026,11,10))
        self.client.force_login(self.user)

    def sale(self, quantity):
        return self.client.post(reverse('revenue-list'),{'production':self.production.pk,'quantity':quantity,'price_per_unit':'5','date':'2026-11-12'})

    def test_sale_deducts_stock_and_appears_in_production_history(self):
        response=self.sale('30')
        self.assertEqual(response.status_code,201,response.content)
        sale=Revenue.objects.get()
        self.assertEqual((sale.revenue_type,sale.branch_id,sale.flock_id,sale.unit),('eggs',self.branch.pk,self.flock.pk,'eggs'))
        self.assertEqual(sale.total_amount,Decimal('150'))
        self.assertEqual(self.production.available_quantity,70)
        self.production.refresh_from_db();self.assertEqual(self.production.quantity,100)
        stock=self.client.get(reverse('revenue-available-production')).json()
        self.assertEqual(Decimal(stock[0]['available_quantity']),70)
        page=self.client.get(reverse('production_records'))
        self.assertEqual(page.context['sales_history'][0].pk,sale.pk)
        self.assertContains(page,'Production Sales History')

    def test_overselling_and_invalid_values_do_not_create_revenue(self):
        for amount in ('101','0','-1'):
            self.assertEqual(self.sale(amount).status_code,400)
        self.assertEqual(Revenue.objects.count(),0)
        self.assertEqual(self.production.available_quantity,100)
        self.assertEqual(self.sale('100').status_code,201)
        self.assertEqual(self.client.get(reverse('revenue-available-production')).json(),[])
        self.assertEqual(self.sale('1').status_code,400)

    def test_edit_delete_sale_updates_availability_and_protects_production(self):
        self.sale('30');sale=Revenue.objects.get()
        self.assertEqual(self.client.patch(reverse('revenue-detail',args=[sale.pk]),{'quantity':'40'},content_type='application/json').status_code,200)
        self.assertEqual(self.production.available_quantity,60)
        self.assertEqual(self.client.patch(reverse('production-detail',args=[self.production.pk]),{'quantity':'20'},content_type='application/json').status_code,400)
        self.assertEqual(self.client.delete(reverse('production-detail',args=[self.production.pk])).status_code,400)
        self.assertEqual(self.client.delete(reverse('revenue-detail',args=[sale.pk])).status_code,204)
        self.assertEqual(self.production.available_quantity,100)

    def test_owned_active_production_is_required(self):
        self.assertEqual(self.client.post(reverse('revenue-list'),{'quantity':1,'price_per_unit':5,'date':'2026-11-12'}).status_code,400)
        other=get_user_model().objects.create_user(username='production-sales-other',password='password123')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('revenue-available-production')).json(),[])
        self.assertEqual(self.sale('1').status_code,400)
        self.client.force_login(self.user)
        self.flock.status='inactive';self.flock.save()
        self.assertEqual(self.client.get(reverse('revenue-available-production')).json(),[])
        self.assertEqual(self.sale('1').status_code,400)

    def test_sale_cannot_predate_production(self):
        response=self.client.post(reverse('revenue-list'),{'production':self.production.pk,'quantity':1,'price_per_unit':5,'date':'2026-11-01'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.production.available_quantity,100)

    def test_whole_account_deletion_does_not_break_existing_admin_workflow(self):
        self.assertEqual(self.sale('20').status_code,201)
        self.user.delete()
        self.assertEqual(Revenue.objects.count(),0)
        self.assertEqual(ProductionRecord.objects.count(),0)
