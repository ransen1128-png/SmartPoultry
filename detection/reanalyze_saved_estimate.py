"""Locally rerun an explicitly selected saved photograph, preserving its old result."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
import torch
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from core.models import RoosterAgeEstimate
from core.views import rooster_age_estimator_view


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('estimate_id', type=int)
    parser.add_argument('--age-model', choices=['original', 'finetuned'], default='original')
    args = parser.parse_args()
    torch.set_num_threads(4)
    original = RoosterAgeEstimate.objects.select_related('user').get(pk=args.estimate_id)
    previous_analysis = original.analysis
    with original.photo.open('rb') as stream:
        image_hash = hashlib.sha256(stream.read()).hexdigest()
    request = RequestFactory().post('/rooster-age-estimator/', {'reanalyze_estimate_id': str(original.pk), 'age_model': args.age_model})
    request.user = original.user
    request.session = {}
    request._messages = FallbackStorage(request)
    response = rooster_age_estimator_view(request)
    assert response.status_code == 302, response.status_code
    new_id = int(parse_qs(urlparse(response.url).query)['estimate'][0])
    latest = RoosterAgeEstimate.objects.get(pk=new_id)
    original.refresh_from_db()
    assert original.analysis == previous_analysis
    with latest.photo.open('rb') as stream:
        assert hashlib.sha256(stream.read()).hexdigest() == image_hash
    report = {'original_id': original.pk, 'new_id': new_id,
              'url': 'http://127.0.0.1:8000' + response.url,
              'original_preserved': True, 'source_photo_sha256': image_hash,
              'age_model': latest.analysis.get('age_model'),
              'age_prediction': latest.analysis.get('age_prediction'),
              'original_age_prediction': latest.analysis.get('original_age_prediction'),
              'chicken_assessment': latest.analysis['chicken_assessment'],
              'chicken_detection': latest.analysis['chicken_detection'],
              'legs': len(latest.analysis['anatomy']['legs']),
              'suppressed_leg_candidates': len(latest.analysis['anatomy'].get('out_of_body_leg_candidates', []))}
    (ROOT / f'detection/smoke/reanalysis_{original.pk}.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
