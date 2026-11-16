import copy
import hashlib
import json
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from unittest.mock import patch

from core.models import RoosterAgeEstimate


class MeasurementReviewTests(TestCase):
    def setUp(self):
        folder=tempfile.mkdtemp();self.addCleanup(shutil.rmtree,folder)
        config=override_settings(MEDIA_ROOT=folder);config.enable();self.addCleanup(config.disable)
        self.user=get_user_model().objects.create_user(username='measurement-review-owner')
        self.other=get_user_model().objects.create_user(username='measurement-review-other')
        self.client.force_login(self.user)
        stream=BytesIO();Image.new('RGB',(200,200),'white').save(stream,format='PNG');self.content=stream.getvalue()
        self.original={'image_quality':{'quality':'good','width':200,'height':200},
                       'age_prediction':{'age_months':13.1,'test_mae_months':1.2},
                       'anatomy':{'status':'completed','legs':[],'spurs':[],'masks':[],'measurements':[],'message':'Synthetic unit fixture'}}
        self.record=RoosterAgeEstimate.objects.create(user=self.user,
            photo=SimpleUploadedFile('synthetic-review-test.png',self.content,content_type='image/png'),
            photo_name='synthetic-review-test.png',estimated_age_range='Synthetic test estimate',analysis=copy.deepcopy(self.original))
        self.url=reverse('review_spur_measurement',args=[self.record.pk])
        self.data={'review_data':json.dumps({'polygon':[[20,50],[150,50],[150,70],[20,70]],'base':[20,60],'tip':[150,60]}),
                   'visible_confirmation':'on','pixels_per_cm':'10','source_sha256':hashlib.sha256(self.content).hexdigest()}

    def test_owner_can_review_without_running_models(self):
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Trace outline')
        self.record.refresh_from_db();self.assertEqual(self.record.analysis,self.original)

    def test_saved_api_failure_is_visible_without_expanding_model_details(self):
        self.record.analysis['anatomy']['api_spur_assistance']={
            'status':'error','message':'Gemini HTTP 403: API key is not permitted.',
            'model':'gemini-3.1-flash-lite','attempts':1}
        self.record.save(update_fields=['analysis'])
        response=self.client.get(reverse('rooster_age_estimator'),{'estimate':self.record.pk})
        self.assertContains(response,'data-spur-api-error')
        html=response.content.decode()
        self.assertLess(html.index('Spur API request failed:'),html.index('<details>'))
        self.assertContains(response,'Gemini HTTP 403: API key is not permitted.')
        self.assertContains(response,'The age result is retained.')

    def test_review_preserves_models_age_and_photo_and_keeps_an_audit_history(self):
        self.assertEqual(self.client.post(self.url,self.data).status_code,302)
        self.record.refresh_from_db();analysis=self.record.analysis
        self.assertEqual(analysis['anatomy'],self.original['anatomy'])
        self.assertEqual(analysis['age_prediction'],self.original['age_prediction'])
        self.assertEqual(self.record.estimated_age_range,'Synthetic test estimate')
        review=analysis['spur_review'];self.assertEqual(review['reviewer_user_id'],self.user.pk)
        self.assertFalse(review['training_consent'])
        self.assertAlmostEqual(review['measurement']['length_px'],130,delta=5)
        self.assertAlmostEqual(review['measurement']['physical_length_cm'],13,delta=.5)
        self.assertEqual(review['measurement']['base'],[20,60])
        self.assertEqual(len(analysis['spur_review_history']),1)
        with self.record.photo.open('rb') as stream:self.assertEqual(stream.read(),self.content)
        self.client.post(self.url,self.data);self.record.refresh_from_db()
        self.assertEqual(len(self.record.analysis['spur_review_history']),2)
        saved=self.client.get(reverse('rooster_age_estimator'),{'estimate':self.record.pk})
        self.assertContains(saved,'User-reviewed base-to-tip curve')
        self.assertEqual(saved.context['results'][0]['reviewed_measurement']['base'],[20,60])

    def test_other_users_cannot_read_or_write_a_review(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.assertEqual(self.client.post(self.url,self.data).status_code,404)
        self.client.logout();self.assertEqual(self.client.get(self.url).status_code,302)

    def test_csrf_is_enforced(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url,self.data).status_code,403)

    def test_unconfirmed_invalid_stale_or_hidden_endpoints_do_not_save_measurements(self):
        cases=[{**self.data,'visible_confirmation':''},{**self.data,'source_sha256':'stale'},
               {**self.data,'pixels_per_cm':'-1'},
               {**self.data,'review_data':'{"polygon":[[20,50],[150,50],[150,70]],"base":null,"tip":[150,60]}'},
               {**self.data,'review_data':json.dumps({'polygon':[[20,50],[150,50],[150,70],[20,70]],'base':[0,0],'tip':[150,60]})}]
        for data in cases:
            self.assertEqual(self.client.post(self.url,data).status_code,400)
            self.record.refresh_from_db();self.assertEqual(self.record.analysis,self.original)

    def test_api_geometry_is_an_unsaved_draft_until_reviewed_with_signed_provenance(self):
        proposal={'status':'completed','regions':[{'xyxy':[20,50,150,70],
            'polygon':[[20,50],[150,50],[150,70],[20,70]],'base':[20,60],'tip':[150,60]}],
            'model':'recorded-api-test','prompt_sha256':'test-policy','message':'API draft; review required.'}
        with patch('core.vision_api.is_configured',return_value=True),patch('core.geometry_api.propose_geometry',return_value=proposal) as call:
            response=self.client.post(self.url,{'action':'api_suggest','source_sha256':self.data['source_sha256']})
        self.assertEqual(response.status_code,200);call.assert_called_once()
        self.assertEqual(response.context['initial']['base'],[20,60])
        token=response.context['draft_token'];self.assertTrue(token)
        self.record.refresh_from_db();self.assertEqual(self.record.analysis,self.original)
        self.assertEqual(self.client.post(self.url,{**self.data,'draft_token':'tampered'}).status_code,400)
        self.record.refresh_from_db();self.assertEqual(self.record.analysis,self.original)
        self.assertEqual(self.client.post(self.url,{**self.data,'draft_token':token}).status_code,302)
        self.record.refresh_from_db();event=self.record.analysis['spur_review']
        self.assertEqual(event['draft_provenance']['source'],'gemini_api_draft')
        self.assertEqual(event['draft_provenance']['user_id'],self.user.pk)
        self.assertEqual(event['source'],'user_reviewed')
