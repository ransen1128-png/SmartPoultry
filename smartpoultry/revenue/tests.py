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
        return self.client.post(reverse('revenue-list'),{'buyer_name':'Test buyer','production':self.production.pk,'quantity':quantity,'price_per_unit':'5','date':'2026-11-12'})

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
        response=self.client.post(reverse('revenue-list'),{'buyer_name':'Buyer','production':self.production.pk,'quantity':1,'price_per_unit':5,'date':'2026-11-01'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.production.available_quantity,100)

    def test_buyer_details_and_order_are_saved_and_transaction_reference_is_stable(self):
        payload={'production':self.production.pk,'quantity':'2','price_per_unit':'5','date':'2026-11-12',
                 'buyer_name':'Buyer One','buyer_contact':'buyer@example.com','buyer_address':'Main Street','order_number':'ORDER-101','transaction_number':'fake-reference'}
        result=self.client.post(reverse('revenue-list'),payload)
        self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(result.data['buyer_name'],'Buyer One')
        self.assertEqual(result.data['buyer_contact'],'buyer@example.com')
        self.assertEqual(result.data['buyer_address'],'Main Street')
        self.assertEqual(result.data['order_number'],'ORDER-101')
        reference=result.data['transaction_number'];self.assertTrue(reference.startswith('TXN-'))
        detail=reverse('revenue-detail',args=[result.data['id']])
        changed=self.client.patch(detail,{'quantity':'3','transaction_number':'replacement'},content_type='application/json')
        self.assertEqual(changed.status_code,200,changed.content)
        self.assertEqual(changed.data['transaction_number'],reference)
        self.assertEqual(self.production.available_quantity,97)
        another=self.sale('1');self.assertNotEqual(another.data['transaction_number'],reference)
        self.assertTrue(another.data['order_number'].startswith('ORD-'))
        from core.models import TransactionRecord
        self.assertTrue(TransactionRecord.objects.filter(metadata__transaction_number=reference).exists())
        other=get_user_model().objects.create_user(username='buyer-outsider')
        self.client.force_login(other)
        self.assertEqual(self.client.get(detail).status_code,404)

    def test_missing_or_blank_buyer_rejected_without_deducting_stock(self):
        payload={'production':self.production.pk,'quantity':'2','price_per_unit':'5','date':'2026-11-12'}
        for buyer in (None,'','   '):
            data=payload if buyer is None else {**payload,'buyer_name':buyer}
            response=self.client.post(reverse('revenue-list'),data)
            self.assertEqual(response.status_code,400)
            self.assertIn('buyer_name',response.data)
        self.assertEqual(self.production.available_quantity,100)
        self.assertFalse(Revenue.objects.exists())

    def test_broiler_sale_captures_buyer_and_references(self):
        flock=Flock.objects.create(user=self.user,branch=self.branch,flock_id='BROILER',breed='broilers',quantity=10,placement_date=date(2026,9,1))
        batch=ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=flock,product_type='meat',quantity=5,unit='birds',date=date(2026,11,10))
        result=self.client.post(reverse('revenue-list'),{'production':batch.pk,'quantity':'2','price_per_unit':'100','date':'2026-11-12','buyer_name':'Broiler buyer'})
        self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(result.data['revenue_type'],'meat')
        self.assertEqual(result.data['buyer_name'],'Broiler buyer')
        self.assertTrue(result.data['transaction_number'].startswith('TXN-'))
        self.assertEqual(batch.available_quantity,3)

    def test_whole_account_deletion_does_not_break_existing_admin_workflow(self):
        self.assertEqual(self.sale('20').status_code,201)
        self.user.delete()
        self.assertEqual(Revenue.objects.count(),0)
        self.assertEqual(ProductionRecord.objects.count(),0)

    def test_review_and_confirm_legacy_sale_preserves_amount_and_records_audit(self):
        from core.models import TransactionRecord
        sale=Revenue.objects.create(user=self.user,revenue_type='eggs',quantity=20,unit='eggs',price_per_unit=5,date=date(2026,11,12))
        report=self.client.get(reverse('revenue-legacy-production')).json()
        self.assertEqual(report[0]['id'],sale.pk)
        self.assertEqual(report[0]['candidates'][0]['id'],self.production.pk)
        result=self.client.post(reverse('revenue-reconcile',args=[sale.pk]),{'production':self.production.pk})
        self.assertEqual(result.status_code,200,result.content)
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount,100)
        self.assertEqual(sale.quantity,20)
        self.assertEqual(self.production.available_quantity,80)
        self.assertTrue(any('reconciliation' in item.metadata for item in TransactionRecord.objects.all()))
        self.assertEqual(self.client.post(reverse('revenue-reconcile',args=[sale.pk]),{'production':self.production.pk}).status_code,400)

    def test_legacy_conversion_and_other_owner_are_not_guessed(self):
        sale=Revenue.objects.create(user=self.user,revenue_type='eggs',quantity=1,unit='tray',price_per_unit=150,date=date(2026,11,12))
        report=self.client.get(reverse('revenue-legacy-production')).json()
        self.assertEqual(report[0]['candidates'],[])
        self.assertEqual(self.client.post(reverse('revenue-reconcile',args=[sale.pk]),{'production':self.production.pk}).status_code,400)
        other=get_user_model().objects.create_user(username='legacy-other',password='password123')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('revenue-legacy-production')).json(),[])
        self.assertEqual(self.client.post(reverse('revenue-reconcile',args=[sale.pk]),{'production':self.production.pk}).status_code,404)
