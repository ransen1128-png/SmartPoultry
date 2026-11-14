from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Farm,Branch
from inventory.models import Inventory,InventoryDistribution
from inventory.quantities import measurement_totals
from expenses.models import Expense
from notifications.models import Notification
from flocks.models import Flock


class InventoryPackagingTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='packaging-owner')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='North')
        Flock.objects.create(user=self.user,branch=self.branch,flock_id='Ready',breed='other',quantity=10)
        self.client.force_login(self.user)

    def create(self,**changes):
        return self.client.post(reverse('inventory-list'),{'item_type':'feed','name':'Feed','quantity':'5','unit':'sacks','package_size':'25','content_unit':'kg','cost_per_unit':'1000',**changes})

    def test_sacks_and_vitamins_keep_package_count_separate_from_content(self):
        feed=self.create();self.assertEqual(feed.status_code,201,feed.content)
        vitamins=self.create(item_type='medicine',name='Vitamins',unit='bottles',content_unit='ml',cost_per_unit='100')
        self.assertEqual(vitamins.status_code,201,vitamins.content)
        for response in (feed,vitamins):
            self.assertEqual(Decimal(response.data['quantity']),5)
            self.assertEqual(Decimal(response.data['total_content']),125)
        self.assertEqual(Decimal(feed.data['total_value']),5000)
        self.assertEqual(Decimal(vitamins.data['total_value']),500)
        totals=measurement_totals(Inventory.objects.filter(user=self.user))
        self.assertEqual({row['unit']:row['quantity'] for row in totals},{'kg':Decimal('125'),'ml':Decimal('125')})

    def test_distribution_deducts_sacks_and_expenses_per_sack_and_keeps_package_snapshot(self):
        item=Inventory.objects.get(pk=self.create().data['id'])
        result=self.client.post(reverse('inventory-distribution-list'),{'inventory':item.pk,'branch':self.branch.pk,'quantity':'2','date':'2026-11-14'})
        self.assertEqual(result.status_code,201,result.content)
        item.refresh_from_db();self.assertEqual((item.quantity,item.total_content),(Decimal('3'),Decimal('75')))
        expense=Expense.objects.get(inventory_distribution_id=result.data['id']);self.assertEqual(expense.amount,2000)
        self.assertEqual(Expense.objects.get(inventory_purchase=item).amount,3000)
        row=InventoryDistribution.objects.get(pk=result.data['id'])
        self.assertEqual((row.package_size_snapshot,row.content_unit_snapshot,row.measurement_quantity),(Decimal('25'),'kg',Decimal('50')))
        correction=self.client.patch(reverse('inventory-detail',args=[item.pk]),{'package_size':'50','content_unit':'kg'},content_type='application/json')
        self.assertEqual(correction.status_code,200,correction.content)
        row.refresh_from_db();self.assertEqual(row.package_size_snapshot,25)
        self.assertEqual(self.client.post(reverse('inventory-distribution-reverse',args=[row.pk]),{'reason':'Return packages'}).status_code,200)
        item.refresh_from_db();self.assertEqual(item.quantity,5)

    def test_invalid_or_partial_package_definition_does_not_create_stock_or_expenses(self):
        for changes in ({'package_size':'0'},{'package_size':'-1'},{'package_size':'','content_unit':'kg'},{'content_unit':''}):
            result=self.create(**changes)
            self.assertEqual(result.status_code,400,result.content)
        self.assertFalse(Inventory.objects.exists())
        self.assertFalse(Expense.objects.exists())

    def test_expense_quantity_and_unit_cost_preserve_distribution_details(self):
        item=Inventory.objects.get(pk=self.create().data['id'])
        row=InventoryDistribution.objects.create(user=self.user,inventory=item,branch=self.branch,quantity=Decimal('2'),date=date(2026,11,14))
        expense=row.expense
        item.cost_per_unit=Decimal('2000');item.package_size=Decimal('50');item.unit='bags';item.save()
        response=self.client.get(reverse('expense-detail',args=[expense.pk]))
        self.assertEqual(response.status_code,200)
        self.assertEqual(Decimal(response.data['item_quantity']),2)
        self.assertEqual(response.data['item_unit'],'sacks')
        self.assertEqual(Decimal(response.data['item_unit_cost']),1000)
        self.assertEqual(Decimal(response.data['item_package_size']),25)
        self.assertEqual(response.data['item_content_unit'],'kg')
        self.assertEqual(Decimal(response.data['amount']),2000)
        row.reverse(self.user,'Return')
        response=self.client.get(reverse('expense-detail',args=[expense.pk]))
        self.assertEqual(Decimal(response.data['amount']),0)
        self.assertEqual(Decimal(response.data['item_quantity']),2)
        self.assertIsNotNone(response.data['distribution_reversed_at'])
        manual=Expense.objects.create(user=self.user,branch=self.branch,expense_type='labor',description='Work',amount=100,date=date(2026,11,14))
        response=self.client.get(reverse('expense-detail',args=[manual.pk]))
        self.assertIsNone(response.data['item_quantity'])
        self.assertIsNone(response.data['item_unit_cost'])

    def test_bulk_stock_stays_in_its_native_unit_without_fake_package_size(self):
        result=self.create(unit='kg',package_size='',content_unit='')
        self.assertEqual(result.status_code,201,result.content)
        item=Inventory.objects.get(pk=result.data['id'])
        self.assertIsNone(item.package_size)
        self.assertIsNone(item.total_content)
        self.assertEqual(item.measurement_quantity,5)
        self.assertEqual(item.measurement_unit,'kg')

    def test_dashboard_and_branch_deliveries_use_explicit_content_units(self):
        item=Inventory.objects.get(pk=self.create().data['id'])
        InventoryDistribution.objects.create(user=self.user,inventory=item,branch=self.branch,quantity=Decimal('2'),date=date(2026,11,14))
        response=self.client.get(reverse('dashboard'),{'month':11,'year':2026})
        self.assertEqual(response.context['metrics']['feed_stock_by_unit'],[{'unit':'kg','quantity':Decimal('75')}])
        report=self.client.get(reverse('report-feed-usage'),{'start':'2026-11-01','end':'2026-11-30'})
        self.assertEqual(Decimal(report.data['results'][0]['quantities']['kg']),50)

    def test_branch_distribution_warns_at_minimum_with_package_units_and_branch(self):
        item=Inventory.objects.get(pk=self.create(minimum_stock='3').data['id'])
        url=reverse('inventory-distribution-list')
        payload={'inventory':item.pk,'branch':self.branch.pk,'date':'2026-11-14'}
        above=self.client.post(url,{**payload,'quantity':'1'})
        self.assertEqual(above.status_code,201,above.content)
        self.assertIsNone(above.data['stock_warning'])
        at_minimum=self.client.post(url,{**payload,'quantity':'1'})
        self.assertEqual(at_minimum.status_code,201,at_minimum.content)
        self.assertIn('3.00 sacks remaining',at_minimum.data['stock_warning'])
        self.assertIn('75.00000 kg',at_minimum.data['stock_warning'])
        self.assertIn('North',at_minimum.data['stock_warning'])
        notices=Notification.objects.filter(user=self.user,notification_type='warning',related_object_id=item.pk,related_object_type='Inventory')
        self.assertEqual(notices.count(),1)
        self.assertIn('North',notices.get().message)
        depleted=self.client.post(url,{**payload,'quantity':'3'})
        self.assertEqual(depleted.status_code,201,depleted.content)
        self.assertIn('0.00 sacks remaining',depleted.data['stock_warning'])
        self.assertEqual(notices.count(),1)
        rejected=self.client.post(url,{**payload,'quantity':'1'})
        self.assertEqual(rejected.status_code,400)
        self.assertEqual(notices.count(),1)
