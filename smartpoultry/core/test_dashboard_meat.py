from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Farm,Branch
from flocks.models import Flock
from production.models import ProductionRecord


class DashboardMeatProductionTests(TestCase):
    def test_meat_is_filtered_by_owner_branch_month_and_keeps_units_separate(self):
        user=get_user_model().objects.create_user(username='meat-dashboard')
        other=get_user_model().objects.create_user(username='meat-dashboard-other')
        farm=Farm.objects.create(owner=user,name='Farm',location='Town',established_date=date(2026,1,1),contact_email='a@example.com',contact_phone='123')
        north=Branch.objects.create(farm=farm,name='North');south=Branch.objects.create(farm=farm,name='South')
        a=Flock.objects.create(user=user,branch=north,flock_id='A',breed='broilers',quantity=100)
        b=Flock.objects.create(user=user,branch=south,flock_id='B',breed='broilers',quantity=100)
        foreign=Flock.objects.create(user=other,flock_id='C',breed='broilers',quantity=100)
        def record(owner,flock,branch,amount,unit,day):
            ProductionRecord.objects.create(user=owner,flock=flock,branch=branch,product_type='meat_ready',quantity=amount,unit=unit,date=day)
        record(user,a,north,10,'units',date(2026,11,10))
        record(user,a,north,Decimal('2.5'),'kg',date(2026,11,11))
        record(user,b,south,20,'units',date(2026,11,10))
        record(user,a,north,5,'units',date(2026,10,10))
        record(other,foreign,None,70,'units',date(2026,11,10))
        self.client.force_login(user)
        params={'month':11,'year':2026}
        response=self.client.get(reverse('dashboard'),params)
        self.assertEqual({row['unit']:row['total'] for row in response.context['metrics']['meat_production']},{'kg':Decimal('2.5'),'units':Decimal('30')})
        response=self.client.get(reverse('dashboard'),{**params,'branch':north.pk})
        self.assertEqual({row['unit']:row['total'] for row in response.context['metrics']['meat_production']},{'kg':Decimal('2.5'),'units':Decimal('10')})
        self.assertContains(response,'Meat')
        self.assertContains(response,'Eggs')
