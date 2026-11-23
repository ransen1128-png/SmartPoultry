"""EXIF-orientation handling, upload limits and health-check exposure."""
import importlib.util,os,shutil,tempfile
from io import BytesIO
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from django.urls import reverse
from core import free_inference as free
from core.models import RoosterAgeEstimate
from core.views import analyze_rooster_photo

FIXTURE=Path(__file__).parent/'testdata/full_chicken.jpg'
ONNX_AVAILABLE=importlib.util.find_spec('onnxruntime') is not None and free.model_files_present('age')


def png(image,orientation=None):
    stream=BytesIO();exif=Image.Exif()
    if orientation:exif[274]=orientation
    image.save(stream,format='PNG',exif=exif);stream.seek(0)
    return stream


def upright_and_phone_style():
    """Return the same photo upright and as a phone stores it: pixels rotated, EXIF orientation 6."""
    with Image.open(FIXTURE) as source:upright=source.convert('RGB')
    # Orientation 6 tells viewers to rotate 90 degrees clockwise (ROTATE_270) to display.
    stored=upright.transpose(Image.Transpose.ROTATE_90)
    return upright,stored


class ExifOrientationTests(TestCase):
    def test_quality_check_reports_upright_dimensions(self):
        upright,stored=upright_and_phone_style()
        result=analyze_rooster_photo(png(stored,orientation=6))
        self.assertEqual((result['width'],result['height']),upright.size)

    @skipUnless(ONNX_AVAILABLE,'onnxruntime and ONNX age model required')
    def test_age_prediction_matches_upright_photo_when_rotation_is_only_in_exif(self):
        upright,stored=upright_and_phone_style()
        expected=free.predict_age(png(upright))
        tagged=free.predict_age(png(stored,orientation=6))
        untagged_sideways=free.predict_age(png(stored))
        self.assertIsNotNone(expected)
        self.assertEqual(tagged['age_months'],expected['age_months'])
        # Guard the test itself: the sideways view must actually change the output.
        self.assertNotEqual(untagged_sideways['age_months'],expected['age_months'])


class EstimatorUploadLimitTests(TestCase):
    def setUp(self):
        self.folder=tempfile.mkdtemp();self.addCleanup(shutil.rmtree,self.folder)
        media=override_settings(MEDIA_ROOT=self.folder,ROOSTER_ESTIMATOR_MAX_PHOTOS=2);media.enable();self.addCleanup(media.disable)
        self.user=get_user_model().objects.create_user(username='limit-owner')
        self.client.force_login(self.user)

    def test_batch_over_limit_is_rejected_before_any_analysis(self):
        photos=[SimpleUploadedFile(f'p{i}.png',png(Image.new('RGB',(32,32))).getvalue(),content_type='image/png') for i in range(3)]
        with patch('core.chicken_detection.detect_chicken',side_effect=AssertionError('Analysis ran')),\
             patch('core.chicken_detection.load_detector',return_value=None),\
             patch('core.poultry_vision.vision_is_ready',return_value=False):
            response=self.client.post(reverse('rooster_age_estimator'),{'analysis_mode':'full','photos':photos})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Upload at most 2 photos at a time. You selected 3.')
        self.assertFalse(RoosterAgeEstimate.objects.filter(user=self.user).exists())

    def test_form_advertises_limit_to_the_browser(self):
        self.assertContains(self.client.get(reverse('rooster_age_estimator')),'data-max-files="2"')


class HealthCheckExposureTests(TestCase):
    def test_anonymous_health_check_reports_liveness_only(self):
        response=self.client.get('/__health/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(set(response.json()),{'ok','marker'})

    def test_staff_health_check_includes_diagnostics(self):
        staff=get_user_model().objects.create_user(username='health-staff',is_staff=True)
        self.client.force_login(staff)
        self.assertIn('database_engine',self.client.get('/__health/').json())

    def test_regular_user_does_not_see_diagnostics(self):
        self.client.force_login(get_user_model().objects.create_user(username='health-user'))
        self.assertNotIn('database_host',self.client.get('/__health/').json())
