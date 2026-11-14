from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.models import Sum
from core.models import Farm,Branch,TransactionRecord
from flocks.models import Flock
from production.models import ProductionRecord
from revenue.models import Revenue
from expenses.models import Expense
from notifications.models import Notification


class ReturnExpenseTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='return-owner')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='North')
        flock=Flock.objects.create(user=self.user,branch=self.branch,flock_id='Layers',breed='layers',quantity=20)
        self.batch=ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=flock,product_type='eggs',egg_size='medium',quantity=20,unit='pcs',date=date(2026,11,1))
        self.sale=Revenue.objects.create(user=self.user,production=self.batch,buyer_name='Buyer',quantity=10,price_per_unit=7,date=date(2026,11,2))
        self.client.force_login(self.user)

    def payload(self,**changes):
        return {'branch':self.branch.pk,'date':'2026-11-26','expense_type':'return_eggs','description':'Spoiled egg','return_quantity':'5','return_unit':'pcs','amount':'35.00',**changes}

    def test_return_eggs_counts_once_in_expenses_without_restocking_or_reducing_revenue(self):
        response=self.client.post(reverse('expense-list'),self.payload())
        self.assertEqual(response.status_code,201,response.content)
        row=Expense.objects.get(pk=response.data['id'])
        self.assertEqual((row.expense_type,row.description,row.return_quantity,row.return_unit,row.amount,row.category),('return_eggs','Spoiled egg',Decimal('5'),'pcs',Decimal('35'),'returns'))
        self.assertEqual(Expense.objects.filter(user=self.user).aggregate(total=Sum('amount'))['total'],35)
        self.assertEqual(self.batch.available_quantity,10)
        self.sale.refresh_from_db();self.assertEqual(self.sale.total_amount,70)
        ledger=TransactionRecord.objects.filter(transaction_type='expense',source_object_id=row.pk,action='created',metadata__expense_type='return_eggs')
        self.assertEqual(ledger.count(),1)
        self.assertEqual(Decimal(ledger.get().metadata['return_quantity']),5)
        dashboard=self.client.get(reverse('dashboard'),{'branch':self.branch.pk,'month':11,'year':2026})
        self.assertEqual(dashboard.context['metrics']['expenses'],35)
        report=self.client.get(reverse('report-branch-expenses'),{'branch':self.branch.pk,'start':'2026-11-01','end':'2026-11-30'})
        self.assertEqual(Decimal(report.data['total']),35)

    def test_item_returns_require_item_name_and_store_units(self):
        missing=self.client.post(reverse('expense-list'),self.payload(expense_type='return_item'))
        self.assertEqual(missing.status_code,400,missing.content)
        result=self.client.post(reverse('expense-list'),self.payload(expense_type='return_item',return_item_name='Vitamins',return_quantity='2',return_unit='bottles',description='Damaged bottles',amount='100'))
        self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(result.data['return_item_name'],'Vitamins')
        self.assertEqual(result.data['return_unit'],'bottles')

    def test_invalid_returns_rejected_without_orphan_expense_or_notification(self):
        notice_count=Notification.objects.filter(user=self.user).count()
        for changes in ({'return_quantity':'0'},{'return_quantity':'-1'},{'return_quantity':''},{'return_unit':''},{'description':' '},{'amount':'-1'},{'branch':''}):
            result=self.client.post(reverse('expense-list'),self.payload(**changes))
            self.assertEqual(result.status_code,400,result.content)
        self.assertFalse(Expense.objects.filter(user=self.user).exists())
        self.assertEqual(Notification.objects.filter(user=self.user).count(),notice_count)

    def test_return_is_owner_scoped_and_cannot_use_inactive_branch(self):
        result=self.client.post(reverse('expense-list'),self.payload());self.assertEqual(result.status_code,201,result.content)
        other=get_user_model().objects.create_user(username='return-outsider');self.client.force_login(other)
        detail=reverse('expense-detail',args=[result.data['id']])
        self.assertEqual(self.client.get(detail).status_code,404)
        self.assertEqual(self.client.delete(detail).status_code,404)
        self.assertEqual(self.client.post(reverse('expense-list'),self.payload()).status_code,400)
        self.client.force_login(self.user);self.branch.status='inactive';self.branch.save()
        self.assertEqual(self.client.post(reverse('expense-list'),self.payload()).status_code,400)
