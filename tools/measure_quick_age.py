"""Measure actual PostgreSQL upload workflow; roll back generated test results."""
import os,sys,time,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
import django
django.setup()
from django.db import transaction
from django.test import Client,override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import RoosterAgeEstimate
before=RoosterAgeEstimate.objects.count()
results=[]
with tempfile.TemporaryDirectory() as media,transaction.atomic(),override_settings(MEDIA_ROOT=media,ALLOWED_HOSTS=['testserver']):
    client=Client();client.force_login(get_user_model().objects.filter(is_active=True).first())
    for name in ['4months.jpg','19months.jpg']:
        image=(ROOT/'spurs images'/name).read_bytes()
        start=time.perf_counter()
        response=client.post('/rooster-age-estimator/',{'analysis_mode':'age_only','photos':[SimpleUploadedFile('new-photo.jpg',image,content_type='image/jpeg')]})
        elapsed=time.perf_counter()-start
        assert response.status_code==200
        record=RoosterAgeEstimate.objects.latest('pk')
        assert record.analysis['anatomy']['status']=='not_run'
        assert record.analysis['age_prediction']
        results.append({'seconds':round(elapsed,3),'age_months':record.analysis['age_prediction']['age_months'],'mode':'age_only'})
    transaction.set_rollback(True)
assert RoosterAgeEstimate.objects.count()==before
(ROOT/'.postgres-migration/quick-age-timings.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
