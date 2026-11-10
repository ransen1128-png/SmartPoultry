from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock, patch

import torch
from PIL import Image

from core.chicken_detection import detect_chicken


class ChickenDetectionTests(TestCase):
    def photo(self):
        stream = BytesIO()
        Image.new('RGB', (100, 80)).save(stream, format='PNG')
        stream.seek(0)
        return stream

    def test_unavailable_is_not_a_negative_detection(self):
        with patch('core.chicken_detection.load_detector', return_value=None):
            self.assertEqual(detect_chicken(self.photo())['status'], 'unavailable')

    def test_real_output_boxes_are_clipped_and_reported(self):
        processor, model = Mock(), Mock()
        processor.return_value = {}
        processor.post_process_object_detection.return_value = [{
            'boxes': torch.tensor([[-2., 3., 110., 70.]]),
            'scores': torch.tensor([0.9]),
        }]
        stream = self.photo()
        with patch('core.chicken_detection.load_detector', return_value=(processor, model)):
            result = detect_chicken(stream)
        self.assertEqual(result['status'], 'detected')
        self.assertEqual(result['boxes'][0]['xyxy'], [0, 3, 100, 70])
        self.assertEqual(stream.tell(), 0)

    def test_empty_output_and_failure_have_different_states(self):
        processor, model = Mock(), Mock()
        processor.return_value = {}
        processor.post_process_object_detection.return_value = [{
            'boxes': torch.empty((0, 4)), 'scores': torch.empty(0),
        }]
        with patch('core.chicken_detection.load_detector', return_value=(processor, model)):
            self.assertEqual(detect_chicken(self.photo())['status'], 'not_detected')
            model.side_effect = RuntimeError('inference failed')
            with self.assertLogs('core.chicken_detection', level='ERROR'):
                self.assertEqual(detect_chicken(self.photo())['status'], 'error')

    def test_young_chicken_query_keeps_lower_score_as_candidate(self):
        processor, model = Mock(), Mock()
        processor.return_value = {}
        processor.post_process_object_detection.return_value = [{
            'boxes': torch.tensor([[0., 10., 90., 80.]]),
            'scores': torch.tensor([.269]), 'labels': torch.tensor([1]),
        }]
        with patch('core.chicken_detection.load_detector', return_value=(processor, model)):
            result = detect_chicken(self.photo())
        self.assertEqual(result['status'], 'candidate')
        self.assertEqual(result['boxes'][0]['query'], 'a young chicken')
