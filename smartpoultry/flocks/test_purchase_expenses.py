from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Farm,Branch,TransactionRecord
from expenses.models import Expense
from flocks.models import Flock
from production.models import ProductionRecord,MortalityRecord


class FlockPurchaseExpenseTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='flock-purchase-owner')
        farm=Farm.objects.create(owner=self.user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        self.branch=Branch.objects.create(farm=farm,name='North')
        self.south=Branch.objects.create(farm=farm,name='South')
        self.client.force_login(self.user)

    def payload(self,**changes):
        return {'placement_date':'2026-09-01','branch':self.branch.pk,'flock_id':'BOUGHT-1','breed':'broilers','quantity':20,'acquisition_source':'purchased','purchase_amount':'1000','delivery_cost':'100','purchase_date':'2026-11-14','supplier':'Delivery supplier',**changes}

    def test_purchase_creates_one_branch_expense_with_delivery_and_audit(self):
        response=self.client.post(reverse('flock-list'),self.payload())
        self.assertEqual(response.status_code,201,response.content)
        expense=Expense.objects.get(flock_purchase_id=response.data['id'])
        self.assertEqual((expense.user,expense.branch,expense.amount,expense.date),(self.user,self.branch,Decimal('1100'),date(2026,11,14)))
        self.assertEqual(expense.expense_type,'flock_purchase')
        self.assertTrue(TransactionRecord.objects.filter(transaction_type='expense',metadata__flock_purchase_id=response.data['id']).exists())

    def test_own_or_unspecified_flock_creates_no_purchase_expense(self):
        for source in ('own','unknown'):
            response=self.client.post(reverse('flock-list'),self.payload(flock_id=source,acquisition_source=source,purchase_amount=0,delivery_cost=0,purchase_date=''))
            self.assertEqual(response.status_code,201,response.content)
        self.assertFalse(Expense.objects.exists())

    def test_mortality_and_production_do_not_reduce_purchase_cost(self):
        response=self.client.post(reverse('flock-list'),self.payload())
        flock=Flock.objects.get(pk=response.data['id'])
        MortalityRecord.objects.create(user=self.user,branch=self.branch,flock=flock,quantity=2,date=date(2026,11,14))
        flock.refresh_from_db()
        ProductionRecord.objects.create(user=self.user,branch=self.branch,flock=flock,product_type='meat_ready',quantity=18,date=date(2026,11,14))
        self.assertEqual(Expense.objects.get(flock_purchase=flock).amount,Decimal('1100'))
        self.assertEqual(Expense.objects.count(),1)

    def test_purchase_correction_updates_existing_expense_without_duplicates(self):
        response=self.client.post(reverse('flock-list'),self.payload());flock_id=response.data['id']
        pk=Expense.objects.get().pk
        result=self.client.patch(reverse('flock-detail',args=[flock_id]),{'branch':self.south.pk,'purchase_amount':'1200'},content_type='application/json')
        self.assertEqual(result.status_code,200,result.content)
        expense=Expense.objects.get();self.assertEqual((expense.pk,expense.amount,expense.branch),(pk,Decimal('1300'),self.south))
        self.assertEqual(self.client.delete(reverse('expense-detail',args=[pk])).status_code,400)
        self.assertEqual(self.client.delete(reverse('flock-detail',args=[flock_id])).status_code,400)
        result=self.client.patch(reverse('flock-detail',args=[flock_id]),{'acquisition_source':'own','purchase_amount':'0','delivery_cost':'0'},content_type='application/json')
        self.assertEqual(result.status_code,200,result.content)
        expense.refresh_from_db();self.assertEqual(expense.amount,0)

    def test_invalid_purchase_rolls_back_the_flock(self):
        for changes in ({'purchase_date':''},{'purchase_amount':'-1'},{'branch':''},{'purchase_amount':'0','delivery_cost':'0'}):
            result=self.client.post(reverse('flock-list'),self.payload(**changes))
            self.assertEqual(result.status_code,400,result.content)
        self.assertFalse(Flock.objects.exists())
        self.assertFalse(Expense.objects.exists())
