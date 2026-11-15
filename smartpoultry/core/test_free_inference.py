import builtins,json,os,shutil,tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase as UnitTestCase
from unittest.mock import patch
import numpy as np
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from django.urls import reverse
from core import free_inference as free
from core.models import RoosterAgeEstimate


class FreeGeometryTests(UnitTestCase):
    def test_nms_suppresses_same_class_and_preserves_other_classes(self):
        boxes=np.array([[0,0,10,10],[1,1,10,10],[0,0,10,10]],dtype=np.float32)
        result=free.nms(boxes,np.array([.9,.8,.7]),.45,12,np.array([0,0,1]))
        self.assertEqual(result.tolist(),[0,2])
        self.assertEqual(free.nms(np.empty((0,4)),np.empty(0),.45,12).tolist(),[])

    def test_large_images_are_rejected_before_decoding(self):
        with self.assertRaises(ValueError):free.check_image_size(SimpleNamespace(width=5000,height=4000,size=(5000,4000)))
        free.check_image_size(SimpleNamespace(width=4000,height=3000,size=(4000,3000)))

    def test_corrupt_asset_is_not_reported_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'age.onnx').write_bytes(b'broken')
            (root/'manifest.json').write_text(json.dumps({'files':[{'filename':'age.onnx','bytes':6,'sha256':'0'*64}]}))
            free.manifest.cache_clear();free.verified_file.cache_clear()
            try:
                with patch.object(free,'MODELS',root):self.assertFalse(free.ready('age'))
            finally:free.manifest.cache_clear();free.verified_file.cache_clear()


class FreeHostedEstimatorTests(TestCase):
    def setUp(self):
        self.folder=tempfile.mkdtemp();self.addCleanup(shutil.rmtree,self.folder)
        settings=override_settings(MEDIA_ROOT=self.folder);settings.enable();self.addCleanup(settings.disable)
        env=patch.dict(os.environ,{'SMARTPOULTRY_INFERENCE_RUNTIME':'onnx'});env.start();self.addCleanup(env.stop)
        self.user=get_user_model().objects.create_user(username='onnx-estimator-owner')
        self.client.force_login(self.user)

    def test_full_upload_runs_without_heavy_libraries_and_saves_real_outputs(self):
        real_import=builtins.__import__
        def reject_heavy(name,*args,**kwargs):
            if name.split('.')[0] in ('torch','torchvision','transformers','ultralytics'):raise AssertionError('Heavy hosted import: '+name)
            return real_import(name,*args,**kwargs)
        content=(Path(__file__).resolve().parents[2]/'spurs images/4months.jpg').read_bytes()
        with patch('builtins.__import__',side_effect=reject_heavy),patch('core.vision_deployment.memory_limit_mb',return_value=512):
            response=self.client.post(reverse('rooster_age_estimator'),{'analysis_mode':'full','photos':[SimpleUploadedFile('arbitrary-name.jpg',content,content_type='image/jpeg')]})
        self.assertEqual(response.status_code,200)
        row=RoosterAgeEstimate.objects.get(user=self.user)
        self.assertEqual(row.analysis['age_prediction']['age_months'],2.5)
        self.assertEqual(row.analysis['age_prediction']['runtime'],'onnx-fp32')
        self.assertEqual(row.analysis['anatomy']['status'],'completed')
        self.assertEqual(row.analysis['chicken_detection']['runtime'],'onnx-int8')
        self.assertTrue(row.analysis['anatomy']['legs'])
        self.assertEqual(self.client.get(reverse('rooster_age_estimator'),{'estimate':row.pk}).status_code,200)

    def test_quick_mode_does_not_run_detectors(self):
        content=(Path(__file__).resolve().parents[2]/'spurs images/4months.jpg').read_bytes()
        with patch.object(free,'detect_chicken',side_effect=AssertionError('Body ran')),patch.object(free,'analyze_anatomy',side_effect=AssertionError('Anatomy ran')):
            response=self.client.post(reverse('rooster_age_estimator'),{'analysis_mode':'age_only','photos':[SimpleUploadedFile('image.jpg',content,content_type='image/jpeg')]})
        self.assertEqual(response.status_code,200)
        row=RoosterAgeEstimate.objects.get(user=self.user)
        self.assertEqual(row.analysis['age_prediction']['age_months'],2.5)
        self.assertEqual(row.analysis['anatomy']['status'],'not_run')

    def test_second_estimation_request_is_rejected_without_writing(self):
        from core.age_inference import _REQUEST_SLOT
        _REQUEST_SLOT.acquire()
        try:response=self.client.post(reverse('rooster_age_estimator'),{'analysis_mode':'full'})
        finally:_REQUEST_SLOT.release()
        self.assertEqual(response.status_code,302)
        self.assertFalse(RoosterAgeEstimate.objects.filter(user=self.user).exists())

    def test_health_does_not_hash_models_or_import_inference_runtime(self):
        with patch.object(free,'ready',side_effect=AssertionError('Heavy readiness called')):
            response=self.client.get('/__health/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['vision_deployment']['inference_runtime'],'onnx')
