from datetime import timedelta
from decimal import Decimal
from django.test import TestCase,TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.db import connection
from unittest import skipUnless
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from core.models import Farm,Branch,AuditEvent,MutationReceipt
from flocks.models import Flock
from inventory.models import Inventory,InventoryDistribution,InventoryUsage
from production.models import ProductionRecord
from revenue.models import Revenue
from expenses.models import Expense
from notifications.models import Notification,NotificationPreference
from notifications.readiness import notify_ready_flocks


def fixture(case):
    case.user=get_user_model().objects.create_user(username='business-owner',password='Test-password-123')
    farm=Farm.objects.create(owner=case.user,name='Test farm',location='Test',established_date=timezone.localdate(),contact_email='test@example.com',contact_phone='123')
    case.branch=Branch.objects.create(farm=farm,name='Branch A')
    case.flock=Flock.objects.create(user=case.user,branch=case.branch,flock_id='LAY-1',breed='layers',quantity=20)
    case.stock=Inventory.objects.create(user=case.user,name='Test feeds',item_type='feed',quantity=10,unit='sacks',cost_per_unit=100,package_size=25,content_unit='kg')
    case.production=ProductionRecord.objects.create(user=case.user,branch=case.branch,flock=case.flock,product_type='eggs',quantity=50,unit='eggs',date=timezone.localdate())
    case.client.force_login(case.user)


class BusinessWorkflowTests(TestCase):
    def setUp(self):fixture(self)

    def distribute(self,quantity=5,key=None):
        return self.client.post('/api/inventory/distributions/',{'inventory':self.stock.pk,'branch':self.branch.pk,'quantity':quantity,'date':str(timezone.localdate())},content_type='application/json',**({'HTTP_IDEMPOTENCY_KEY':key} if key else {}))

    def sale_payload(self):
        return {'buyer_name':'Receipt buyer','order_number':'SAME-TYPED-ORDER','date':str(timezone.localdate()),'items':[{'production':self.production.pk,'quantity':2,'price_per_unit':5},{'production':self.production.pk,'quantity':3,'price_per_unit':6}]}

    def test_distribution_retry_deducts_and_allocates_once(self):
        first=self.distribute(key='retry-1');second=self.distribute(key='retry-1')
        self.assertEqual(first.status_code,201,first.content);self.assertEqual(first.json(),second.json())
        self.assertEqual(second['Idempotency-Replayed'],'true')
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,5)
        self.assertEqual(InventoryDistribution.objects.count(),1)
        self.assertEqual(Expense.objects.filter(inventory_distribution__isnull=False).count(),1)
        self.assertEqual(self.distribute(2,key='retry-1').status_code,409)

    def test_distributing_everything_reports_zero_without_a_minimum(self):
        self.assertIsNone(self.stock.minimum_stock)
        response=self.distribute(10,key='all-stock')
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(Decimal(response.json()['remaining_quantity']),0)
        self.assertIsNone(response.json()['stock_warning'])
        self.assertEqual(response.json()['item_name'],'Test feeds')

    def test_order_retry_and_receipt_grouping(self):
        payload=self.sale_payload()
        first=self.client.post('/api/revenue/order/',payload,content_type='application/json',HTTP_IDEMPOTENCY_KEY='sale-1')
        second=self.client.post('/api/revenue/order/',payload,content_type='application/json',HTTP_IDEMPOTENCY_KEY='sale-1')
        self.assertEqual(first.status_code,201,first.content);self.assertEqual(first.json(),second.json())
        self.assertEqual(Revenue.objects.count(),2);self.assertEqual(self.production.available_quantity,45)
        receipt=self.client.get(reverse('sales_receipt',args=[first.json()['items'][0]['id']]))
        self.assertEqual(len(receipt.context['rows']),2);self.assertEqual(receipt.context['total'],28)
        # Another order with the same user-entered number must remain separate.
        self.client.post('/api/revenue/order/',payload,content_type='application/json',HTTP_IDEMPOTENCY_KEY='sale-2')
        receipt=self.client.get(reverse('sales_receipt',args=[first.json()['items'][0]['id']]))
        self.assertEqual(len(receipt.context['rows']),2)
        other=get_user_model().objects.create_user(username='other-owner');self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('sales_receipt',args=[first.json()['items'][0]['id']])).status_code,404)

    def test_failed_order_not_cached_and_no_partial_sales(self):
        payload=self.sale_payload();payload['items'][1]['quantity']=100
        result=self.client.post('/api/revenue/order/',payload,content_type='application/json',HTTP_IDEMPOTENCY_KEY='bad-order')
        self.assertEqual(result.status_code,400);self.assertFalse(Revenue.objects.exists());self.assertFalse(MutationReceipt.objects.exists())

    def test_usage_balances_and_reversal_never_add_an_expense(self):
        lot=self.distribute().json()['id'];cost=sum(Expense.objects.values_list('amount',flat=True))
        payload={'distribution':lot,'quantity':'2','date':str(timezone.localdate()),'reason':'Daily feeding'}
        result=self.client.post('/api/inventory/usage/',payload,content_type='application/json',HTTP_IDEMPOTENCY_KEY='use-1')
        retry=self.client.post('/api/inventory/usage/',payload,content_type='application/json',HTTP_IDEMPOTENCY_KEY='use-1')
        self.assertEqual(result.status_code,201,result.content);self.assertEqual(result.json(),retry.json())
        balance=self.client.get('/api/inventory/distributions/branch-stock/').json()[0]
        self.assertEqual(Decimal(balance['remaining']),3);self.assertEqual(Decimal(balance['used']),2)
        self.assertEqual(sum(Expense.objects.values_list('amount',flat=True)),cost)
        self.assertEqual(self.client.post(f'/api/inventory/distributions/{lot}/reverse/',{'reason':'Wrong lot'}).status_code,400)
        self.assertEqual(self.client.post('/api/inventory/usage/',{**payload,'quantity':4},content_type='application/json').status_code,400)
        reversal=self.client.post(f'/api/inventory/usage/{result.json()["id"]}/reverse/',{'reason':'Correction'})
        self.assertEqual(reversal.status_code,200,reversal.content)
        self.assertEqual(self.client.post(f'/api/inventory/distributions/{lot}/reverse/',{'reason':'Wrong lot'}).status_code,200)
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,10)
        self.assertFalse(self.client.get('/api/inventory/distributions/branch-stock/').json())

    def test_foreign_usage_and_future_usage_rejected(self):
        lot=self.distribute().json()['id']
        payload={'distribution':lot,'quantity':1,'date':str(timezone.localdate()+timedelta(days=1)),'reason':'Test'}
        self.assertEqual(self.client.post('/api/inventory/usage/',payload,content_type='application/json').status_code,400)
        other=get_user_model().objects.create_user(username='usage-outsider');self.client.force_login(other)
        payload['date']=str(timezone.localdate())
        self.assertEqual(self.client.post('/api/inventory/usage/',payload,content_type='application/json').status_code,400)
        self.assertFalse(self.client.get('/api/inventory/distributions/branch-stock/').json())

    def test_audit_actor_before_after_and_append_only_note(self):
        self.client.patch(f'/api/inventory/items/{self.stock.pk}/',{'minimum_stock':'3','correction_reason':'Reorder threshold approved'},content_type='application/json')
        event=AuditEvent.objects.filter(object_type='inventory.Inventory',object_id=self.stock.pk,action='updated').latest('pk')
        self.assertEqual(event.actor_id,self.user.pk);self.assertIsNone(event.before['minimum_stock'])
        self.assertEqual(event.after['minimum_stock'],'3.00');self.assertEqual(event.reason,'Reorder threshold approved')
        self.client.post(reverse('activity_history'),{'event':event.pk,'reason':'Reviewed by owner'})
        event.refresh_from_db();self.assertEqual(event.reason,'Reorder threshold approved')
        self.assertTrue(AuditEvent.objects.filter(action='note',reason='Reviewed by owner').exists())
        other=get_user_model().objects.create_user(username='audit-outsider');self.client.force_login(other)
        self.assertNotContains(self.client.get(reverse('activity_history')),'Reorder threshold approved')
        self.assertEqual(self.client.post(reverse('activity_history'),{'event':event.pk,'reason':'Other'}).status_code,404)

    def test_readiness_day_25_only_once_and_respects_preferences(self):
        self.flock.breed='broilers';self.flock.placement_date=timezone.localdate()-timedelta(days=24);self.flock.save()
        self.assertEqual(notify_ready_flocks(self.user),0)
        self.flock.placement_date-=timedelta(days=1);self.flock.save()
        self.assertEqual(notify_ready_flocks(self.user),1);self.assertEqual(notify_ready_flocks(self.user),0)
        self.assertEqual(Notification.objects.filter(deduplication_key__isnull=False).count(),1)
        NotificationPreference.objects.create(user=self.user,in_app_notifications=False)
        self.flock.placement_date-=timedelta(days=1);self.flock.save()
        self.assertEqual(notify_ready_flocks(self.user),0)


@skipUnless(connection.vendor=='postgresql','PostgreSQL row-lock concurrency test')
class ConcurrentMutationTests(TransactionTestCase):
    def setUp(self):fixture(self)

    def test_simultaneous_retry_has_one_distribution(self):
        from rest_framework.test import APIClient
        from django.db import connections
        barrier=Barrier(2)
        def submit(_):
            try:
                client=APIClient();client.force_authenticate(self.user);barrier.wait(timeout=10)
                response=client.post('/api/inventory/distributions/',{'inventory':self.stock.pk,'branch':self.branch.pk,'quantity':7,'date':str(timezone.localdate())},format='json',HTTP_IDEMPOTENCY_KEY='parallel-1')
                return response.status_code,response.json()
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(submit,range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(results[0][0],201)
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,3)
        self.assertEqual(InventoryDistribution.objects.count(),1)


class AgeIntervalDisplayTests(TestCase):
    def test_no_artifact_means_no_claimed_range(self):
        from core.evaluation_status import tested_age_range
        self.assertIn('unavailable',tested_age_range(None))

    def test_verified_matching_artifact_and_checkpoint_are_required(self):
        import hashlib,json
        from core.evaluation_status import tested_age_range
        evaluation=json.dumps({'independent_evaluation_executed':True,'provenance_sha256':'synthetic-provenance','checkpoint_sha256':'synthetic-model'}).encode()
        interval={'status':'tested','evaluation_sha256':hashlib.sha256(evaluation).hexdigest(),'checkpoint_sha256':'synthetic-model',
            'calibration_chickens':20,'test_chickens':20,'radius_months':2,'held_out_bird_coverage':.9}
        with patch('core.evaluation_status.Path.read_bytes',return_value=evaluation),patch('core.evaluation_status.Path.read_text',return_value=json.dumps(interval)):
            self.assertIn('8.0–12.0 months',tested_age_range({'age_months':10,'model_sha256':'synthetic-model'}))
            self.assertIn('unavailable',tested_age_range({'age_months':10,'model_sha256':'another-model'}))
