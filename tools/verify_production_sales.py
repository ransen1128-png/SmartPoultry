"""Actual PostgreSQL sale smoke check; all temporary records are rolled back."""
import os
import sys
import secrets
import json
from pathlib import Path
from datetime import date
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
import django
django.setup()
from django.db import transaction,connection
from django.test import Client,override_settings
from django.contrib.auth import get_user_model
from core.models import Farm,Branch
from flocks.models import Flock
from production.models import ProductionRecord
from revenue.models import Revenue
assert connection.vendor=='postgresql'
before=(get_user_model().objects.count(),Revenue.objects.count(),ProductionRecord.objects.count())
with transaction.atomic(),override_settings(ALLOWED_HOSTS=['testserver','127.0.0.1']):
    user=get_user_model().objects.create_user(username='sale-check-'+secrets.token_hex(6),password=secrets.token_urlsafe(24))
    farm=Farm.objects.create(owner=user,name='Verification',location='Local',established_date=date(2026,1,1),contact_email='check@example.invalid',contact_phone='0')
    branch=Branch.objects.create(farm=farm,name='Verification')
    flock=Flock.objects.create(user=user,branch=branch,flock_id='CHECK',breed='layers',quantity=50)
    record=ProductionRecord.objects.create(user=user,branch=branch,flock=flock,product_type='eggs',quantity=100,date=date(2026,11,12))
    client=Client();client.force_login(user)
    payload={'production':record.pk,'quantity':'30','price_per_unit':'5','date':'2026-11-12'}
    result=client.post('/api/revenue/',payload)
    assert result.status_code==201,result.content
    assert record.available_quantity==70
    result=client.post('/api/revenue/',{**payload,'quantity':'71'})
    assert result.status_code==400,result.content
    assert record.available_quantity==70
    assert client.get('/production-records/').status_code==200
    assert client.get('/api/revenue/available-production/').status_code==200
    transaction.set_rollback(True)
assert before==(get_user_model().objects.count(),Revenue.objects.count(),ProductionRecord.objects.count())
report={'engine':'postgresql','sale_deducted_available_stock':True,'oversell_rejected':True,'history_page_http':200,'all_temporary_data_rolled_back':True}
(ROOT/'.postgres-migration/production-sales-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
