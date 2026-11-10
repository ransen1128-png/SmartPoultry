"""Actual upload/save/reopen smoke test, rolling back database and temporary media."""
import json
import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
import torch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import Client, override_settings
from django.urls import reverse
from core.models import RoosterAgeEstimate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='19months.jpg')
    args = parser.parse_args()
    torch.set_num_threads(4)
    user = get_user_model().objects.filter(is_active=True).first()
    if user is None:
        raise RuntimeError('No existing active user for smoke test')
    image = ROOT / 'spurs images' / args.image
    with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media, ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1']), transaction.atomic():
        client = Client()
        client.force_login(user)
        before = RoosterAgeEstimate.objects.count()
        response = client.post(reverse('rooster_age_estimator'), {'photos': SimpleUploadedFile('smoke.jpg', image.read_bytes(), content_type='image/jpeg')})
        assert response.status_code == 200, response.status_code
        assert RoosterAgeEstimate.objects.count() == before + 1
        record = RoosterAgeEstimate.objects.latest('pk')
        assert record.analysis['anatomy']['status'] == 'completed'
        assert record.analysis['age_prediction'] is not None
        assert record.analysis['chicken_detection']['status'] not in ('unavailable', 'error')
        subject = record.analysis['chicken_assessment']
        assert subject['label'].encode() in response.content
        if record.analysis['chicken_detection']['status'] == 'not_detected' and record.analysis['anatomy']['spurs']:
            assert subject['status'] == 'anatomy_candidate'
        reopened = client.get(reverse('rooster_age_estimator'), {'estimate': record.pk})
        assert reopened.status_code == 200
        preview_url = reverse('rooster_estimate_photo', args=[record.pk])
        preview = client.get(preview_url)
        assert preview.status_code == 200
        preview.close()
        assert Client().get(preview_url).status_code == 302
        result = {'source_image': image.name, 'upload_http': response.status_code, 'saved_analysis_http': reopened.status_code,
                  'preview_http': preview.status_code, 'anonymous_preview_http': 302,
                  'age': record.analysis['age_prediction'], 'anatomy': record.analysis['anatomy'],
                  'chicken_detection': record.analysis['chicken_detection'],
                  'chicken_assessment': subject,
                  'database_changes_rolled_back': True, 'media': 'temporary, automatically removed'}
        transaction.set_rollback(True)
    filename = 'django_workflow.json' if args.image == '19months.jpg' else f'django_workflow_{image.stem}.json'
    (ROOT / 'detection/smoke' / filename).write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ('anatomy', 'chicken_detection')}, indent=2))


if __name__ == '__main__':
    main()
