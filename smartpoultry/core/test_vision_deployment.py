from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
from core.vision_deployment import memory_warning
from core.poultry_vision import analyze_poultry,assess_chicken_evidence
from core.chicken_detection import detect_chicken


class VisionDeploymentTests(TestCase):
    def test_small_instance_reports_capacity_without_loading_models(self):
        with patch('core.vision_deployment.memory_limit_mb',return_value=512),patch('core.chicken_detection.load_detector',side_effect=AssertionError('Body model loaded')),patch('core.poultry_vision.load_vision_models',side_effect=AssertionError('Anatomy model loaded')):
            body=detect_chicken(BytesIO(b'not read'))
            anatomy=analyze_poultry(BytesIO(b'not read'))
        self.assertEqual(body['status'],'unavailable')
        self.assertEqual(anatomy['status'],'unavailable')
        self.assertIn('512 MB',body['message'])
        self.assertEqual(assess_chicken_evidence(body,anatomy)['label'],'Detection unavailable')

    def test_capacity_check_accepts_two_gb_or_unrestricted_desktop(self):
        for limit in (2048,None):
            with self.subTest(limit=limit),patch('core.vision_deployment.memory_limit_mb',return_value=limit):
                self.assertEqual(memory_warning(),'')
