from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import torch
import numpy as np
from PIL import Image

from core.poultry_vision import _centerline_measurement, analyze_poultry, assess_chicken_evidence, constrain_legs_to_body, summarize_anatomy


class ChickenEvidenceTests(TestCase):
    def test_closeup_anatomy_is_evidence_without_a_body_box(self):
        result = assess_chicken_evidence({'status': 'not_detected', 'boxes': []},
                                         {'status': 'completed', 'legs': [{}], 'spurs': [{}]})
        self.assertEqual(result['status'], 'anatomy_candidate')
        self.assertIn('Possible chicken anatomy: leg/spur', result['label'])
        self.assertNotIn('close-up', result['label'])
        self.assertIn('do not independently verify the species', result['explanation'])

    def test_failed_or_empty_anatomy_is_not_confirmation(self):
        for anatomy in ({'status': 'error', 'legs': [{}]},
                        {'status': 'completed', 'legs': [], 'spurs': [], 'masks': []}):
            self.assertEqual(assess_chicken_evidence({'status': 'not_detected'}, anatomy)['status'], 'unconfirmed')

    def test_body_candidate_requires_an_actual_box(self):
        self.assertEqual(assess_chicken_evidence({'status': 'detected', 'boxes': [{}]}, {})['status'], 'body_candidate')
        self.assertEqual(assess_chicken_evidence({'status': 'detected', 'boxes': []}, {})['status'], 'unconfirmed')

    def test_lower_score_body_candidate_is_not_a_confirmed_yes(self):
        result = assess_chicken_evidence({'status': 'candidate', 'boxes': [{}]}, {})
        self.assertEqual(result['label'], 'Chicken detected')
        self.assertIn('does not confirm chicken presence', result['explanation'])

    def test_outside_body_leg_proposals_are_retained_separately(self):
        anatomy = {'status': 'completed', 'legs': [{'xyxy': [10, 10, 30, 30]}, {'xyxy': [150, 150, 170, 170]}], 'message': 'Ran models.'}
        result = constrain_legs_to_body({'status': 'candidate', 'boxes': [{'xyxy': [0, 0, 100, 100]}]}, anatomy)
        self.assertEqual(len(result['legs']), 1)
        self.assertEqual(len(result['out_of_body_leg_candidates']), 1)
        self.assertEqual(len(anatomy['legs']), 2)
        self.assertIs(constrain_legs_to_body({'status': 'not_detected'}, anatomy), anatomy)


class VisionGeometryTests(TestCase):
    def test_pixel_measurement_requires_explicit_scale_for_centimeters(self):
        polygon = [[20, 30], [80, 30], [80, 40], [20, 40]]
        unscaled = _centerline_measurement(polygon, 100, 80)
        calibrated = _centerline_measurement(polygon, 100, 80, 10.)
        self.assertGreater(unscaled['length_px'], 40)
        self.assertLess(unscaled['length_px'], 70)
        self.assertIsNone(unscaled['physical_length_cm'])
        self.assertAlmostEqual(calibrated['physical_length_cm'], calibrated['length_px']/10, delta=.002)
        self.assertEqual(calibrated['calibration']['source'], 'user_supplied')

    def test_frame_truncated_mask_never_claims_complete_physical_length(self):
        measurement = _centerline_measurement([[0, 20], [60, 20], [60, 30], [0, 30]], 100, 80, 10.)
        self.assertTrue(measurement['truncated_at_frame'])
        self.assertIsNone(measurement['physical_length_cm'])
        self.assertTrue(measurement['centerline'])

    def test_degenerate_polygon_cannot_be_measured(self):
        self.assertIsNone(_centerline_measurement([[1, 1], [2, 2]], 100, 80))


class AnatomyInferenceTests(TestCase):
    def photo(self):
        stream = BytesIO()
        Image.new('RGB', (100, 80), 'white').save(stream, format='PNG')
        stream.seek(0)
        return stream

    def bundle(self, with_mask=True):
        boxes = SimpleNamespace(xyxy=torch.tensor([[-2., 10., 110., 70.], [20., 30., 80., 40.]]),
                                conf=torch.tensor([.8, .9]), cls=torch.tensor([0., 1.]))
        detected = SimpleNamespace(boxes=boxes)
        segmented = SimpleNamespace(masks=SimpleNamespace(xy=[np.array([[20., 30.], [80., 30.], [80., 40.], [20., 40.]])]) if with_mask else None,
                                    boxes=SimpleNamespace(conf=torch.tensor([.85])))
        detector, segmenter = Mock(), Mock()
        detector.predict.return_value = [detected]
        segmenter.predict.return_value = [segmented]
        manifest = {'version': 'test', 'confidence_threshold': .3,
                    'detect': {'sha256': 'test-detector'}, 'segment': {'sha256': 'test-segmenter'}}
        return {'detect': detector, 'segment': segmenter, 'manifest': manifest}

    def test_actual_model_outputs_are_preserved_clipped_and_measured(self):
        stream = self.photo()
        with patch('core.poultry_vision.load_vision_models', return_value=self.bundle()):
            result = analyze_poultry(stream, 10.)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['legs'][0]['xyxy'], [0., 10., 100., 70.])
        self.assertEqual(len(result['spurs']), 1)
        self.assertEqual(len(result['masks']), 1)
        self.assertIsNotNone(result['measurements'][0]['physical_length_cm'])
        self.assertEqual(stream.tell(), 0)

    def test_detection_without_mask_does_not_invent_outline_or_measurement(self):
        with patch('core.poultry_vision.load_vision_models', return_value=self.bundle(with_mask=False)):
            result = analyze_poultry(self.photo())
        self.assertTrue(result['spurs'])
        self.assertFalse(result['masks'])
        self.assertFalse(result['measurements'])
        self.assertIn('No spur mask', summarize_anatomy(result)['spur_segmentation_status'])

    def test_unavailable_model_is_not_a_negative_detection(self):
        with patch('core.poultry_vision.load_vision_models', return_value=None):
            result = analyze_poultry(self.photo())
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(summarize_anatomy(result)['spur_visibility_value'], 'unassessed')

    def test_unmatched_outline_is_not_measured(self):
        bundle = self.bundle()
        bundle['detect'].predict.return_value[0].boxes.cls = torch.tensor([0., 0.])
        with patch('core.poultry_vision.load_vision_models', return_value=bundle):
            result = analyze_poultry(self.photo())
        self.assertTrue(result['unconfirmed_masks'])
        self.assertFalse(result['masks'])
        self.assertFalse(result['measurements'])

    def test_corrupt_upload_and_invalid_scale_fail_without_fake_outputs(self):
        with patch('core.poultry_vision.load_vision_models', return_value=self.bundle()):
            with self.assertLogs('core.poultry_vision', level='ERROR'):
                corrupt = analyze_poultry(BytesIO(b'not an image'))
            with self.assertLogs('core.poultry_vision', level='ERROR'):
                invalid = analyze_poultry(self.photo(), float('nan'))
        self.assertEqual(corrupt['status'], 'error')
        self.assertEqual(invalid['status'], 'error')
        self.assertFalse(corrupt['masks'] or invalid['measurements'])
