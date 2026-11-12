import unittest
import json
from unittest.mock import patch
from PIL import Image
from tools.benchmark_vision_api import parse_detection_response, choose_box, padded_crop, summarize, call_gemini


class DetectionParsingTests(unittest.TestCase):
    def test_parses_valid_box(self):
        detections = parse_detection_response('{"detections":[{"box_2d":[100,200,400,500],"confidence":0.9}]}')
        self.assertEqual(detections[0]["box_2d"], [100, 200, 400, 500])

    def test_rejects_out_of_range_box(self):
        self.assertEqual(parse_detection_response('{"detections":[{"box_2d":[-1,0,400,500]}]}'), [])

    def test_empty_detection_means_no_crop(self):
        self.assertIsNone(choose_box(parse_detection_response('{"detections":[]}')))


    def test_api_request_uses_fixed_host_and_header_key(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps({"detections": []})}]}}]}).encode()

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as mocked:
            result = call_gemini(b"small-image", "image/jpeg", "test-secret", "gemini-test")
        self.assertEqual(result, [])
        request = mocked.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://generativelanguage.googleapis.com/"))
        self.assertEqual(request.get_header("X-goog-api-key"), "test-secret")
        self.assertNotIn("test-secret", request.full_url)

    def test_selects_highest_confidence(self):
        boxes = [
            {"box_2d": [100, 100, 200, 200], "confidence": 0.2},
            {"box_2d": [300, 300, 500, 500], "confidence": 0.8},
        ]
        self.assertEqual(choose_box(boxes), [300, 300, 500, 500])


class CropTests(unittest.TestCase):
    def test_crop_is_inside_original_and_nonempty(self):
        image = Image.new("RGB", (1000, 800))
        crop = padded_crop(image, [100, 200, 400, 500])
        self.assertGreater(crop.width, 0)
        self.assertGreater(crop.height, 0)
        self.assertLessEqual(crop.width, image.width)
        self.assertLessEqual(crop.height, image.height)


class MetricsTests(unittest.TestCase):
    def test_metrics_use_paired_images_for_crop_comparison(self):
        rows = [
            {"actual_age_months": 10, "full_prediction": 12, "crop_prediction": 10.5},
            {"actual_age_months": 12, "full_prediction": 11, "crop_prediction": None},
        ]
        metrics = summarize(rows)
        self.assertEqual(metrics["crop_count"], 1)
        self.assertEqual(metrics["paired_full_image_mae_months"], 2.0)
        self.assertEqual(metrics["spur_crop_mae_months"], 0.5)
        self.assertEqual(metrics["full_image_mae_months"], 1.5)


if __name__ == "__main__":
    unittest.main()
