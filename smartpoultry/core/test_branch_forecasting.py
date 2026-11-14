from datetime import date,timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from core.models import Farm,Branch
from flocks.models import Flock
from revenue.models import Revenue
from expenses.models import Expense
from production.models import ProductionRecord
from inventory.models import Inventory,InventoryDistribution
from core.branch_forecasting import add_months


class BranchForecastTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='branch-forecaster')
        self.other=get_user_model().objects.create_user(username='branch-forecast-other')
        def farm(user,name):return Farm.objects.create(owner=user,name=name,location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        owned=farm(self.user,'Owned');foreign=farm(self.other,'Other')
        self.north=Branch.objects.create(farm=owned,name='North')
        self.south=Branch.objects.create(farm=owned,name='South')
        self.empty=Branch.objects.create(farm=owned,name='Empty')
        self.foreign=Branch.objects.create(farm=foreign,name='Foreign')
        self.today=timezone.localdate()
        self.past_feeds=[]
        for owner,branch,income,cost,birds,eggs in [(self.user,self.north,1000,100,10,10),(self.user,self.south,2000,500,30,20),(self.other,self.foreign,90000,0,500,900)]:
            flock=Flock.objects.create(user=owner,branch=branch,flock_id='01',breed='layers',quantity=birds)
            Revenue.objects.create(user=owner,branch=branch,revenue_type='eggs',quantity=1,price_per_unit=income,date=self.today)
            Expense.objects.create(user=owner,branch=branch,expense_type='feed',description='Assigned cost',amount=cost,date=self.today)
            ProductionRecord.objects.create(user=owner,branch=branch,flock=flock,product_type='eggs',quantity=eggs,unit='eggs',date=self.today)
            for offset in range(1,5):
                past=add_months(self.today.replace(day=1),-offset)
                Revenue.objects.create(user=owner,branch=branch,revenue_type='eggs',quantity=1,price_per_unit=income,date=past)
                Expense.objects.create(user=owner,branch=branch,expense_type='feed',description='Assigned historical cost',amount=cost,date=past)
                ProductionRecord.objects.create(user=owner,branch=branch,flock=flock,product_type='eggs',quantity=eggs,unit='eggs',date=past)
        for offset in range(1,5):
            past=add_months(self.today.replace(day=1),-offset)
            self.past_feeds.append(Inventory.objects.create(user=self.user,item_type='feed',name='Earlier warehouse feed',quantity=5,unit='kg',cost_per_unit=20,date_added=past))
        self.feed=Inventory.objects.create(user=self.user,item_type='feed',name='Warehouse feed',quantity=5,unit='kg',cost_per_unit=20,date_added=self.today)
        Revenue.objects.create(user=self.user,branch=self.north,revenue_type='eggs',quantity=1,price_per_unit=99999,date=self.today+timedelta(days=1))
        self.client.force_login(self.user)

    def test_comparison_has_separate_forecasts_and_unassigned_cost_is_not_given_to_a_branch(self):
        response=self.client.get(reverse('forecasting'))
        self.assertEqual(response.status_code,200)
        rows={row['branch'].pk:row for row in response.context['branch_forecasts']}
        self.assertEqual(set(rows),{self.north.pk,self.south.pk,self.empty.pk})
        self.assertEqual((rows[self.north.pk]['revenue_forecast'],rows[self.north.pk]['expected_profit'],rows[self.north.pk]['feed_demand'],rows[self.north.pk]['production_forecast']),(1000,900,36,10))
        self.assertEqual((rows[self.south.pk]['revenue_forecast'],rows[self.south.pk]['expected_profit'],rows[self.south.pk]['feed_demand'],rows[self.south.pk]['production_forecast']),(2000,1500,108,20))
        self.assertEqual(response.context['expected_profit'],2300)
        self.assertIsNone(rows[self.empty.pk]['revenue_forecast'])
        self.assertEqual(rows[self.empty.pk]['model_reports']['revenue']['status'],'insufficient_history')

    def test_selected_branch_cards_and_chart_use_only_that_branch(self):
        response=self.client.get(reverse('forecasting'),{'branch':self.north.pk})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['selected_branch'],self.north)
        self.assertEqual(response.context['revenue_forecast'],1000)
        self.assertEqual(response.context['expected_profit'],900)
        self.assertEqual(response.context['feed_demand'],36)
        self.assertNotIn(2000,response.context['chart_data']['actualRevenue'])
        self.assertEqual(response.context['chart_data']['forecastRevenue'][-3:],[1000]*3)
        self.assertContains(response,'Feed delivered to this branch')
        self.assertNotContains(response,'kg feed encoded')

    def test_distribution_cost_and_quantity_follow_receiving_branch(self):
        for feed in self.past_feeds:
            InventoryDistribution.objects.create(user=self.user,inventory=feed,branch=self.north,quantity=Decimal('2'),date=feed.date_added)
        InventoryDistribution.objects.create(user=self.user,inventory=self.feed,branch=self.north,quantity=Decimal('2'),date=self.today)
        response=self.client.get(reverse('forecasting'),{'branch':self.north.pk})
        self.assertEqual(response.context['expected_profit'],860)
        self.assertEqual(response.context['feed_deliveries'],[{'unit':'kg','quantity':10.0}])
        response=self.client.get(reverse('forecasting'),{'branch':self.south.pk})
        self.assertEqual(response.context['expected_profit'],1500)
        self.assertEqual(response.context['feed_deliveries'],[])

    def test_other_owner_invalid_and_inactive_branches_are_rejected(self):
        for branch in (self.foreign.pk,'not-a-branch'):
            self.assertEqual(self.client.get(reverse('forecasting'),{'branch':branch}).status_code,404)
        self.empty.status='inactive';self.empty.save()
        self.assertEqual(self.client.get(reverse('forecasting'),{'branch':self.empty.pk}).status_code,404)
