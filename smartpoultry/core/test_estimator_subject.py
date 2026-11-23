import shutil
import tempfile
from io import BytesIO
from unittest.mock import patch

from PIL import Image, ImageDraw
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from .models import RoosterAgeEstimate


class EstimatorSubjectTests(TestCase):
    def setUp(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        settings = override_settings(MEDIA_ROOT=folder)
        settings.enable(); self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_user(username='subject-check-owner')
        self.client.force_login(self.user)
        for target, value in [('core.age_inference.model_is_ready', True),
                              ('core.chicken_detection.load_detector', None),
                              ('core.poultry_vision.vision_is_ready', False),
                              ('core.vision_api.is_configured', False)]:
            mocked = patch(target, return_value=value)
            mocked.start(); self.addCleanup(mocked.stop)

    def photo(self):
        image = Image.new('RGB', (320, 320), 'white')
        draw = ImageDraw.Draw(image)
        for y in range(20, 300, 20): draw.text((20, y), 'Farm records: written notes 123', fill='black')
        data = BytesIO(); image.save(data, format='PNG')
        return SimpleUploadedFile('notebook.png', data.getvalue(), content_type='image/png')

    def anatomy(self, **changes):
        return {'status':'completed', 'legs':[], 'spurs':[], 'masks':[], 'measurements':[],
                'message':'No spur detected.', **changes}

    def detection(self, status='not_detected', score=.9):
        return {'status':status, 'boxes':[] if status not in ('detected','candidate') else
                [{'xyxy':[10, 10, 100, 100], 'score':score}], 'message':'Subject detection result.'}

    def test_both_modes_block_unrelated_weak_leg_only_and_unavailable_results(self):
        cases = [(self.detection(), self.anatomy()),
                 (self.detection('candidate', .26), self.anatomy()),
                 (self.detection(), self.anatomy(legs=[{'xyxy':[10,10,40,80], 'score':.99}])),
                 (self.detection('unavailable'), self.anatomy(status='unavailable'))]
        for mode in ('full', 'age_only'):
            for body, anatomy in cases:
                with self.subTest(mode=mode, body=body['status'], anatomy=anatomy), \
                     patch('core.chicken_detection.detect_chicken', return_value=body), \
                     patch('core.poultry_vision.analyze_poultry', return_value=anatomy), \
                     patch('core.age_inference.predict_rooster_age') as predict:
                    result = self.client.post('/rooster-age-estimator/', {'analysis_mode':mode, 'photos':[self.photo()]})
                predict.assert_not_called()
                self.assertEqual(result.status_code, 200)
                row = RoosterAgeEstimate.objects.filter(user=self.user).latest('pk')
                self.assertIsNone(row.analysis['age_prediction'])
                self.assertFalse(row.analysis['subject_verification']['accepted'])
                self.assertEqual(row.estimated_age_range, 'Insufficient evidence')
                self.assertContains(result, 'a chicken or chicken spur could not be verified')

    def test_quick_chicken_verification_skips_segmentation_but_runs_age(self):
        prediction = {'age_months':12, 'test_mae_months':1}
        with patch('core.chicken_detection.detect_chicken', return_value=self.detection('detected')), \
             patch('core.poultry_vision.analyze_poultry') as anatomy, \
             patch('core.age_inference.predict_rooster_age', return_value=prediction) as predict:
            result = self.client.post('/rooster-age-estimator/', {'analysis_mode':'age_only','photos':[self.photo()]})
        self.assertEqual(result.status_code, 200)
        predict.assert_called_once(); anatomy.assert_not_called()

    def test_quick_spur_closeup_requires_positive_spur_and_requests_detection_only(self):
        anatomy = self.anatomy(spurs=[{'xyxy':[40,40,90,60], 'score':.95}])
        with patch('core.chicken_detection.detect_chicken', return_value=self.detection()), \
             patch('core.poultry_vision.analyze_poultry', return_value=anatomy) as analyze, \
             patch('core.age_inference.predict_rooster_age', return_value={'age_months':12,'test_mae_months':1}) as predict:
            self.client.post('/rooster-age-estimator/', {'analysis_mode':'age_only','photos':[self.photo()]})
        self.assertTrue(analyze.call_args.kwargs['detection_only'])
        predict.assert_called_once()

    def test_legacy_quick_result_is_withheld_without_overwriting_history(self):
        record = RoosterAgeEstimate.objects.create(user=self.user, photo=self.photo(),
            photo_name='notebook.png', estimated_age_range='Experimental estimate: 11.0 months',
            spur_observations='Experimental estimate: 11.0 months',
            analysis={'analysis_mode':'age_only','age_prediction':{'age_months':11,'test_mae_months':1}})
        response = self.client.get('/rooster-age-estimator/', {'estimate':record.pk})
        self.assertNotContains(response, 'Experimental estimate: 11.0 months')
        self.assertContains(response, 'Insufficient evidence')
        record.refresh_from_db()
        self.assertEqual(record.estimated_age_range, 'Experimental estimate: 11.0 months')

    def test_api_spur_requires_completed_assistance_and_a_valid_box(self):
        from .estimator_subject import verify_subject
        anatomy = self.anatomy(spurs=[{'xyxy':[40,40,90,60], 'source':'gemini_api', 'score':None}],
                               api_spur_assistance={'status':'completed'})
        self.assertTrue(verify_subject(self.detection(), anatomy)['accepted'])
        anatomy['api_spur_assistance']['status'] = 'error'
        self.assertFalse(verify_subject(self.detection(), anatomy)['accepted'])
        anatomy['api_spur_assistance']['status'] = 'completed'
        anatomy['spurs'][0]['xyxy'] = [90,60,40,40]
        self.assertFalse(verify_subject(self.detection(), anatomy)['accepted'])
