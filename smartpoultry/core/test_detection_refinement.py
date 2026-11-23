from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock

from PIL import Image

from .detection_refinement import refine_chicken, refine_anatomy
from .estimator_subject import verify_subject


def photo():
    stream = BytesIO(); Image.new('RGB', (400,400), 'white').save(stream, format='PNG'); stream.seek(0)
    return stream


def anatomy(**values):
    return {'status':'completed','legs':[], 'spurs':[], 'masks':[], 'measurements':[], 'message':'Primary analysis.', **values}


class DetectionRefinementTests(TestCase):
    def test_body_recovery_maps_candidate_crop_to_original_pixels(self):
        original = {'status':'candidate', 'boxes':[{'xyxy':[100,100,200,200],'score':.3}]}
        infer = Mock(return_value={'status':'detected','boxes':[{'xyxy':[20,20,120,120],'score':.8}]})
        result = refine_chicken(photo(), original, infer)
        self.assertEqual(result['boxes'][0]['xyxy'], [95,95,195,195])
        self.assertTrue(verify_subject(result, {})['accepted'])
        self.assertEqual(original['status'], 'candidate')
        infer.assert_called_once()

    def test_mirrored_body_maps_back_without_inventing_confidence(self):
        infer = Mock(return_value={'status':'detected','boxes':[{'xyxy':[10,20,100,200],'score':.81}]})
        result = refine_chicken(photo(), {'status':'not_detected','boxes':[]}, infer)
        self.assertEqual(result['boxes'][0]['xyxy'], [300,20,390,200])
        self.assertEqual(result['boxes'][0]['score'], .81)

    def test_weak_retry_is_not_promoted_and_ready_body_does_not_retry(self):
        infer = Mock(return_value={'status':'candidate','boxes':[{'xyxy':[10,10,100,100],'score':.3}]})
        result = refine_chicken(photo(), {'status':'not_detected','boxes':[]}, infer)
        self.assertEqual(result['status'], 'not_detected')
        self.assertFalse(verify_subject(result, {})['accepted'])
        infer.reset_mock()
        original = {'status':'detected','boxes':[{'xyxy':[10,10,100,100],'score':.8}]}
        self.assertIs(refine_chicken(photo(), original, infer), original)
        infer.assert_not_called()

    def test_no_anatomy_retries_for_unrelated_or_unavailable_images(self):
        infer = Mock()
        for original in (anatomy(), anatomy(status='unavailable')):
            self.assertIs(refine_anatomy(photo(), {'status':'not_detected'}, original, infer), original)
        infer.assert_not_called()

    def test_crop_recovers_leg_and_corroborated_outline_in_global_coordinates(self):
        original = anatomy(legs=[{'xyxy':[100,100,160,250], 'score':.95}])
        region = {'xyxy':[30,40,55,65], 'score':.95}
        mask = {**region,'polygon':[[30,40],[55,40],[55,65],[30,65]]}
        crop = anatomy(legs=[{'xyxy':[60,50,80,140], 'score':.9}], spurs=[region], masks=[mask],
            measurements=[{'mask_index':0,'length_px':20,'physical_length_cm':2,'centerline':[[30,50],[50,50]], 'truncated_at_frame':False}])
        infer = Mock(return_value=crop)
        result = refine_anatomy(photo(), {'status':'not_detected'}, original, infer, 10)
        self.assertEqual(result['spurs'][0]['xyxy'], [91,42,116,67])
        self.assertEqual(result['masks'][0]['polygon'][0], [91,42])
        measurement = result['measurements'][0]
        self.assertEqual(measurement['centerline'], [[91,52],[111,52]])
        self.assertEqual(measurement['length_px'], 20)
        self.assertEqual(measurement['physical_length_cm'], 2)
        self.assertEqual(measurement['mask_index'], 0)
        self.assertEqual(original['spurs'], [])
        infer.assert_called_once()

    def test_uncorroborated_spurs_are_not_added_and_quick_mode_skips_outlines(self):
        original = anatomy(legs=[{'xyxy':[100,100,160,250], 'score':.95}])
        infer = Mock(return_value=anatomy(spurs=[{'xyxy':[30,40,55,65],'score':.95}]))
        result = refine_anatomy(photo(), {'status':'not_detected'}, original, infer, detection_only=True)
        self.assertEqual(result['spurs'], [])
        self.assertTrue(infer.call_args.kwargs['detection_only'])
        self.assertEqual(result['measurements'], [])

    def test_nested_leg_proposals_are_deduplicated(self):
        original = anatomy(legs=[{'xyxy':[100,100,160,250], 'score':.95}])
        infer = Mock(return_value=anatomy(legs=[{'xyxy':[40,100,90,230],'score':.97}]))
        result = refine_anatomy(photo(), {'status':'not_detected'}, original, infer)
        self.assertEqual(len(result['legs']), 1)

    def test_retry_budget_is_bounded_and_unavailable_crops_preserve_primary(self):
        original = anatomy(legs=[{'xyxy':[10,10,30,100],'score':.95},
                                 {'xyxy':[200,10,230,130],'score':.96},
                                 {'xyxy':[300,10,330,160],'score':.97}])
        infer = Mock(return_value=anatomy(status='unavailable'))
        result = refine_anatomy(photo(), {'status':'not_detected'}, original, infer)
        self.assertEqual(infer.call_count, 2)
        self.assertEqual(result['legs'], original['legs'])
