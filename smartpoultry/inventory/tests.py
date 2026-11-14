from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.models import Sum
from django.core.management import call_command
from core.models import Farm,Branch
from inventory.models import Inventory,InventoryDistribution
from expenses.models import Expense
from flocks.models import Flock


class DistributionExpenseTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='allocation-owner',password='password123')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='North')
        self.other_branch=Branch.objects.create(farm=farm,name='South')
        for branch in (self.branch,self.other_branch):
            Flock.objects.create(user=self.user,branch=branch,flock_id='Ready',breed='other',quantity=10)
        self.item=Inventory.objects.create(user=self.user,item_type='feed',name='Layer feed',quantity=Decimal('100'),unit='kg',cost_per_unit=Decimal('25'),date_added=date(2026,10,1))
        self.client.force_login(self.user)

    def distribute(self,quantity,branch=None):
        return self.client.post(reverse('inventory-distribution-list'),{'inventory':self.item.pk,'branch':(branch or self.branch).pk,'quantity':quantity,'date':'2026-11-13'})

    def total(self):
        return Expense.objects.filter(user=self.user).aggregate(total=Sum('amount'))['total']

    def test_branch_assignment_preserves_total_and_purchase_date(self):
        response=self.distribute('20')
        self.assertEqual(response.status_code,201,response.content)
        expense=Expense.objects.get(inventory_distribution_id=response.data['id'])
        self.assertEqual((expense.branch,expense.amount,expense.date),(self.branch,Decimal('500'),date(2026,10,1)))
        self.assertEqual(expense.inventory_distribution.date,date(2026,11,13))
        self.assertEqual(self.total(),Decimal('2500'))
        self.assertEqual(Expense.objects.get(inventory_purchase=self.item).amount,Decimal('2000'))
        self.assertEqual(self.distribute('30',self.other_branch).status_code,201)
        self.assertEqual(Expense.objects.get(branch=self.other_branch).amount,Decimal('750'))
        self.assertEqual(self.total(),Decimal('2500'))
        branch_dashboard=self.client.get(reverse('dashboard'),{'branch':self.branch.pk,'month':10,'year':2026})
        self.assertEqual(branch_dashboard.context['metrics']['feed_cost'],Decimal('500'))
        result=self.client.get(reverse('expense-list')).json()['results']
        self.assertEqual(next(r for r in result if r['id']==expense.pk)['distribution_date'],'2026-11-13')

    def test_allocation_uses_frozen_price_and_cannot_be_manually_deleted(self):
        self.item.cost_per_unit=Decimal('99');self.item.save()
        response=self.distribute('10')
        expense=Expense.objects.get(inventory_distribution_id=response.data['id'])
        self.assertEqual(expense.amount,Decimal('250'))
        self.assertEqual(self.client.delete(reverse('expense-detail',args=[expense.pk])).status_code,400)
        self.assertEqual(self.client.patch(reverse('expense-detail',args=[expense.pk]),{'amount':'1'},content_type='application/json').status_code,400)
        distribution=expense.inventory_distribution
        distribution.delete()
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity,Decimal('100'))
        self.assertEqual(Expense.objects.get(inventory_purchase=self.item).amount,Decimal('2500'))
        self.assertEqual(self.total(),Decimal('2500'))

    def test_missing_purchase_rolls_back_stock_and_distribution(self):
        Expense.objects.filter(inventory_purchase=self.item).delete()
        response=self.distribute('20')
        self.assertEqual(response.status_code,400,response.content)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity,Decimal('100'))
        self.assertFalse(InventoryDistribution.objects.exists())

    def test_penny_rounding_does_not_create_additional_cost(self):
        tiny=Inventory.objects.create(user=self.user,item_type='medicine',name='Tiny batch',quantity=Decimal('.02'),unit='kg',cost_per_unit=Decimal('.50'))
        for _ in range(2):
            InventoryDistribution.objects.create(user=self.user,inventory=tiny,branch=self.branch,quantity=Decimal('.01'),date=date(2026,11,13))
        self.assertEqual(Expense.objects.filter(inventory_distribution__inventory=tiny).aggregate(total=Sum('amount'))['total'],Decimal('.01'))
        self.assertEqual(Expense.objects.get(inventory_purchase=tiny).amount,Decimal('0'))
        half_cent=Inventory.objects.create(user=self.user,item_type='medicine',name='Half-cent batch',quantity=Decimal('.01'),unit='kg',cost_per_unit=Decimal('.50'))
        distribution=InventoryDistribution.objects.create(user=self.user,inventory=half_cent,branch=self.branch,quantity=Decimal('.01'),date=date(2026,11,13))
        self.assertEqual(distribution.expense.amount,Decimal('.01'))
        self.assertEqual(Expense.objects.get(inventory_purchase=half_cent).amount,Decimal('0'))

    def test_backfill_command_is_idempotent_and_dry_run_is_read_only(self):
        # A bulk-created row represents an older, already deducted distribution.
        InventoryDistribution.objects.bulk_create([InventoryDistribution(user=self.user,inventory=self.item,branch=self.branch,quantity=Decimal('20'),date=date(2026,11,13))])
        self.item.quantity=Decimal('80');self.item.save()
        call_command('allocate_distribution_expenses')
        self.assertFalse(Expense.objects.filter(inventory_distribution__isnull=False).exists())
        call_command('allocate_distribution_expenses',apply=True)
        call_command('allocate_distribution_expenses',apply=True)
        self.assertEqual(Expense.objects.filter(inventory_distribution__isnull=False).count(),1)
        self.assertEqual(self.total(),Decimal('2500'))

    def test_reversing_rounded_allocations_never_creates_negative_new_expenses(self):
        tiny=Inventory.objects.create(user=self.user,item_type='medicine',name='Rounding reversals',quantity=Decimal('.04'),unit='kg',cost_per_unit=Decimal('.49'))
        records=[InventoryDistribution.objects.create(user=self.user,inventory=tiny,branch=self.branch,quantity=Decimal('.01'),date=date(2026,11,13)) for _ in range(4)]
        records[0].delete();records[2].delete()
        for _ in range(2):
            record=InventoryDistribution.objects.create(user=self.user,inventory=tiny,branch=self.branch,quantity=Decimal('.01'),date=date(2026,11,13))
            self.assertGreaterEqual(record.expense.amount,Decimal('0'))
        self.assertEqual(Expense.objects.filter(inventory_distribution__inventory=tiny).aggregate(total=Sum('amount'))['total'],Decimal('.02'))
        self.assertEqual(Expense.objects.get(inventory_purchase=tiny).amount,Decimal('0'))

    def test_inactive_or_other_owner_branch_cannot_receive_cost(self):
        self.branch.status='inactive';self.branch.save()
        self.assertEqual(self.distribute('10').status_code,400)
        other=get_user_model().objects.create_user(username='other-owner')
        self.other_branch.farm.owner=other;self.other_branch.farm.save()
        self.assertEqual(self.distribute('10',self.other_branch).status_code,400)
        self.assertFalse(InventoryDistribution.objects.exists())

    def test_depleted_item_and_records_are_retained_and_reversal_restores_stock(self):
        response=self.distribute('100')
        self.assertEqual(response.status_code,201,response.content)
        self.item.refresh_from_db();self.assertEqual(self.item.quantity,0)
        self.assertEqual(self.client.get(reverse('inventory-detail',args=[self.item.pk])).status_code,200)
        self.assertEqual(self.client.delete(reverse('inventory-detail',args=[self.item.pk])).status_code,400)
        self.assertEqual(Expense.objects.get(inventory_distribution_id=response.data['id']).amount,Decimal('2500'))
        result=self.client.post(reverse('inventory-distribution-reverse',args=[response.data['id']]),{'reason':'Return unused stock'})
        self.assertEqual(result.status_code,200,result.content)
        self.item.refresh_from_db();self.assertEqual(self.item.quantity,100)
        self.assertEqual(self.total(),Decimal('2500'))

    def test_zero_item_without_distributions_is_kept_for_history(self):
        self.item.quantity=Decimal('0');self.item.save()
        self.assertEqual(self.client.delete(reverse('inventory-detail',args=[self.item.pk])).status_code,400)
        self.assertTrue(Inventory.objects.filter(pk=self.item.pk).exists())
