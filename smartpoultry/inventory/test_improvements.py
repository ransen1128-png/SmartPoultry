from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.urls import reverse
from core.models import Farm,Branch
from flocks.models import Flock
from inventory.models import Inventory,InventoryDistribution
from expenses.models import Expense
from notifications.models import Notification,NotificationPreference
from production.models import ProductionRecord


class FarmImprovementTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='improvement-owner')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='North')
        self.south=Branch.objects.create(farm=farm,name='South')
        self.flock=Flock.objects.create(user=self.user,branch=self.branch,flock_id='F1',breed='layers',quantity=20)
        self.item=Inventory.objects.create(user=self.user,item_type='feed',name='Feed',quantity=Decimal('100'),unit='kg',cost_per_unit=Decimal('10'),date_added=date(2026,11,1))
        self.client.force_login(self.user)

    def distribute(self,quantity='20',**overrides):
        data={'inventory':self.item.pk,'branch':self.branch.pk,'flock':self.flock.pk,'quantity':quantity,'date':'2026-11-13',**overrides}
        return self.client.post(reverse('inventory-distribution-list'),data)

    def test_reversal_is_repeat_safe_restores_cost_and_retains_history(self):
        result=self.distribute();self.assertEqual(result.status_code,201,result.content)
        pk=result.data['id'];url=reverse('inventory-distribution-reverse',args=[pk])
        for _ in range(2):
            result=self.client.post(url,{'reason':'Wrong branch'})
            self.assertEqual(result.status_code,200,result.content)
        self.item.refresh_from_db();self.assertEqual(self.item.quantity,100)
        row=InventoryDistribution.objects.get(pk=pk)
        self.assertIsNotNone(row.reversed_at);self.assertEqual(row.reversed_by,self.user)
        self.assertEqual(row.cost_snapshot,200)
        self.assertEqual(row.expense.amount,0)
        self.assertEqual(Expense.objects.get(inventory_purchase=self.item).amount,1000)
        self.assertEqual(Expense.objects.filter(user=self.user).aggregate(total=Sum('amount'))['total'],1000)
        self.assertIn('Wrong branch',row.expense.notes)
        self.assertEqual(self.distribute().status_code,201)

    def test_reversal_needs_reason_and_rejects_another_account(self):
        pk=self.distribute().data['id'];url=reverse('inventory-distribution-reverse',args=[pk])
        self.assertEqual(self.client.post(url,{'reason':' '}).status_code,400)
        self.client.force_login(get_user_model().objects.create_user(username='outsider'))
        self.assertEqual(self.client.post(url,{'reason':'Wrong'}).status_code,404)

    def test_low_stock_warning_is_one_per_episode_and_rearms_after_reversal(self):
        self.item.minimum_stock=Decimal('80');self.item.save()
        result=self.distribute()
        notices=lambda:Notification.objects.filter(user=self.user,related_object_type='Inventory',related_object_id=self.item.pk,notification_type='warning')
        self.assertEqual(notices().count(),1)
        self.item.refresh_from_db();self.item.save();self.assertEqual(notices().count(),1)
        self.client.post(reverse('inventory-distribution-reverse',args=[result.data['id']]),{'reason':'Correction'})
        self.assertEqual(self.distribute().status_code,201)
        self.assertEqual(notices().count(),2)

    def test_stock_threshold_validation_and_notification_preference(self):
        url=reverse('inventory-detail',args=[self.item.pk])
        self.assertEqual(self.client.patch(url,{'minimum_stock':'-1'},content_type='application/json').status_code,400)
        NotificationPreference.objects.update_or_create(user=self.user,defaults={'in_app_notifications':False})
        self.assertEqual(self.client.patch(url,{'minimum_stock':'100'},content_type='application/json').status_code,200)
        self.assertFalse(Notification.objects.filter(user=self.user,notification_type='warning').exists())

    def test_flock_must_belong_to_receiving_branch(self):
        self.assertEqual(self.distribute(branch=self.south.pk).status_code,400)
        self.assertFalse(InventoryDistribution.objects.exists())

    def test_branch_without_ready_flocks_rejects_distribution_without_side_effects(self):
        for status,quantity in ((None,None),('inactive',20),('active',0),('sold',20),('deceased',20),('retired',20)):
            with self.subTest(status=status,quantity=quantity):
                if status is not None:
                    self.flock.status=status;self.flock.quantity=quantity;self.flock.save()
                branch=self.south if status is None else self.branch
                before_expenses=list(Expense.objects.order_by('pk').values_list('pk','amount'))
                before_notifications=Notification.objects.count()
                result=self.distribute(branch=branch.pk,flock='')
                self.assertEqual(result.status_code,400,result.content)
                self.assertIn('no active flock with chicken',str(result.data['branch']))
                self.item.refresh_from_db();self.assertEqual(self.item.quantity,100)
                self.assertFalse(InventoryDistribution.objects.filter(user=self.user).exists())
                self.assertEqual(list(Expense.objects.order_by('pk').values_list('pk','amount')),before_expenses)
                self.assertEqual(Notification.objects.count(),before_notifications)

    def test_branch_distribution_without_flock_selection_resumes_after_activation(self):
        self.flock.status='inactive';self.flock.save()
        self.assertEqual(self.distribute(flock='').status_code,400)
        self.flock.status='active';self.flock.save()
        self.assertEqual(self.distribute(flock='').status_code,201)

    def test_flock_with_no_live_birds_cannot_receive_inventory(self):
        self.flock.quantity=0;self.flock.save()
        self.assertEqual(self.distribute().status_code,400)
        self.item.refresh_from_db();self.assertEqual(self.item.quantity,100)
        self.assertFalse(InventoryDistribution.objects.exists())

    def test_reports_scope_dates_branch_and_preserve_all_branch_total(self):
        self.distribute()
        url=reverse('report-branch-expenses')
        params={'start':'2026-11-01','end':'2026-11-30'}
        all_result=self.client.get(url,params);self.assertEqual(all_result.status_code,200,all_result.content)
        self.assertEqual(Decimal(all_result.data['total']),1000)
        result=self.client.get(url,{**params,'branch':self.branch.pk})
        self.assertEqual(Decimal(result.data['total']),200)
        self.assertEqual(Decimal(self.client.get(url,{**params,'branch':'unassigned'}).data['total']),800)
        csv_result=self.client.get(url,{**params,'branch':self.branch.pk,'export':'csv'})
        self.assertIn('North',csv_result.content.decode());self.assertNotIn('Inventory purchase',csv_result.content.decode())
        self.assertEqual(self.client.get(url,{'start':'2026-12-01','end':'2026-11-01'}).status_code,400)
        self.client.force_login(get_user_model().objects.create_user(username='report-outsider'))
        self.assertEqual(self.client.get(url,{**params,'branch':self.branch.pk}).status_code,400)
        self.assertEqual(self.client.get(url,params).data['total'],'0')

    def test_feed_report_uses_delivery_dates_and_excludes_reversals(self):
        ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=self.flock,product_type='eggs',quantity=100,unit='eggs',date=date(2026,11,13))
        pk=self.distribute().data['id'];url=reverse('report-feed-usage');params={'start':'2026-11-13','end':'2026-11-13'}
        result=self.client.get(url,params);self.assertEqual(result.status_code,200,result.content)
        row=result.data['results'][0]
        self.assertEqual(row['quantities'],{'kg':'20.00'})
        self.assertEqual(row['distributed_feed_cost_per_egg'],'2.0000')
        self.client.post(reverse('inventory-distribution-reverse',args=[pk]),{'reason':'Wrong amount'})
        self.assertEqual(self.client.get(url,params).data['results'],[])

    def test_unknown_flocks_and_trays_do_not_produce_a_fake_cost_per_egg(self):
        self.distribute(flock='')
        ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=self.flock,product_type='eggs',quantity=2,unit='trays',date=date(2026,11,13))
        self.distribute()
        results=self.client.get(reverse('report-feed-usage'),{'start':'2026-11-01','end':'2026-11-30'}).data['results']
        self.assertTrue(results)
        self.assertTrue(all(row['distributed_feed_cost_per_egg'] is None for row in results))
