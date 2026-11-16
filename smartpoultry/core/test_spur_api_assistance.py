import copy
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from PIL import Image

from core.poultry_vision import summarize_anatomy
from core.spur_api_assistance import assist_missed_spurs


class SpurAPIAssistanceTests(TestCase):
    def test_hosted_and_desktop_use_same_tested_default_despite_legacy_model_setting(self):
        for hosted in ('', 'true'):
            with patch.dict('os.environ',{'RENDER':hosted,'GEMINI_VISION_MODEL':'legacy-benchmark-model',
                                         'GEMINI_SPUR_FALLBACK_MODEL':''}),patch('core.spur_api_assistance.locate_spurs',return_value=copy.deepcopy(self.api)) as call:
                result=assist_missed_spurs(self.stream,self.anatomy)
            self.assertEqual(call.call_args.kwargs,{'model':'gemini-3.1-flash-lite','timeout':20,'max_attempts':2})
            self.assertEqual(result['api_spur_assistance']['model'],'gemini-3.1-flash-lite')

    def setUp(self):
        self.stream = BytesIO()
        Image.new('RGB', (300, 300), 'white').save(self.stream, format='PNG')
        self.stream.seek(0)
        self.anatomy = {'status': 'completed', 'legs': [{'xyxy': [139.2, 195.7, 175.9, 240.3], 'score': .7769}],
                        'spurs': [], 'masks': [], 'measurements': [], 'message': 'Local inference completed.'}
        # Recorded successful API localization on the real whole-rooster fixture.
        self.api = {'status': 'completed', 'boxes': [[161.1, 204.6, 183.9, 224.4]], 'model_version': 'recorded-model'}

    def test_actual_boxes_remain_distinct_from_masks_lengths_and_confidence(self):
        original = copy.deepcopy(self.anatomy)
        with patch('core.spur_api_assistance.locate_spurs', return_value=self.api):
            result = assist_missed_spurs(self.stream, self.anatomy)
        self.assertEqual(self.anatomy, original)
        self.assertEqual(len(result['spurs']), 1)
        self.assertIsNone(result['spurs'][0]['score'])
        self.assertEqual(result['spurs'][0]['source'], 'gemini_api')
        self.assertEqual(result['masks'], [])
        self.assertEqual(result['measurements'], [])
        summary = summarize_anatomy(result)
        self.assertIn('Source: Gemini API', summary['spur_detection_status'])
        self.assertIn('no confidence score supplied', summary['spur_location_assessment'])
        self.assertIn('outline is required', summary['spur_length_assessment'])
        self.assertEqual(self.stream.tell(), 0)

    def test_head_and_invalid_proposals_are_not_accepted_as_spurs(self):
        self.api['boxes'] = [[77.9, 53.6, 141.4, 175.7], None, [-1, 0, 5, 5], [1, 1, float('nan'), 2]]
        with patch('core.spur_api_assistance.locate_spurs', return_value=self.api):
            result = assist_missed_spurs(self.stream, self.anatomy)
        self.assertEqual(result['spurs'], [])
        self.assertEqual(result['api_spur_assistance']['accepted_regions'], 0)

    def test_existing_spurs_and_unavailable_anatomy_do_not_call_api(self):
        for changes in ({'spurs': [{}]}, {'masks': [{}]}, {'legs': []}, {'status': 'error'}):
            anatomy = {**self.anatomy, **changes}
            with patch('core.spur_api_assistance.locate_spurs') as call:
                self.assertIs(assist_missed_spurs(self.stream, anatomy), anatomy)
            call.assert_not_called()

    def test_api_empty_or_failed_results_preserve_local_outputs(self):
        for api in ({'status': 'completed', 'boxes': []}, {'status': 'error', 'boxes': [], 'message': 'Timed out.'}):
            with patch('core.spur_api_assistance.locate_spurs', return_value=api):
                result = assist_missed_spurs(self.stream, self.anatomy)
            self.assertEqual(result['legs'], self.anatomy['legs'])
            self.assertEqual(result['spurs'], [])
            self.assertFalse(result['measurements'])
            if api['status'] == 'error':
                self.assertIn('API assistance did not complete', summarize_anatomy(result)['spur_detection_status'])

    def test_corrupt_photo_does_not_call_api(self):
        with patch('core.spur_api_assistance.locate_spurs') as call:
            result = assist_missed_spurs(BytesIO(b'bad image'), self.anatomy)
        call.assert_not_called()
        self.assertEqual(result['api_spur_assistance']['status'], 'error')
        self.assertEqual(result['spurs'], [])

    def test_partial_local_results_are_combined_without_duplicates_or_score_boosts(self):
        anatomy = copy.deepcopy(self.anatomy)
        anatomy['legs'].append({'xyxy': [40, 190, 80, 245], 'score': .9})
        local = {'xyxy': [161.1, 204.6, 183.9, 224.4], 'score': .88, 'source': 'experimental_detector'}
        anatomy['spurs'] = [copy.deepcopy(local)]
        api = {**self.api, 'boxes': [local['xyxy'], [55, 205, 85, 225], [56, 206, 84, 224]]}
        with patch('core.spur_api_assistance.locate_spurs', return_value=api):
            result = assist_missed_spurs(self.stream, anatomy)
        self.assertEqual(len(result['spurs']), 2)
        self.assertEqual(result['spurs'][0], local)
        self.assertIsNone(result['spurs'][1]['score'])
        self.assertEqual(result['api_spur_assistance']['local_agreements'], 1)
        self.assertEqual(result['api_spur_assistance']['accepted_regions'], 1)
        self.assertEqual(result['api_spur_assistance']['missing_leg_regions'], [1])
        self.assertIn('Sources: local model and Gemini API', summarize_anatomy(result)['spur_detection_status'])
        self.assertEqual(len(anatomy['spurs']), 1)

    def test_all_legs_with_local_spurs_skip_the_api(self):
        anatomy = copy.deepcopy(self.anatomy)
        anatomy['spurs'] = [{'xyxy': [161, 205, 184, 224], 'score': .9}]
        with patch('core.spur_api_assistance.locate_spurs') as call:
            self.assertIs(assist_missed_spurs(self.stream, anatomy), anatomy)
        call.assert_not_called()

    def test_api_location_can_support_a_real_local_outline_and_calibration(self):
        anatomy = copy.deepcopy(self.anatomy)
        anatomy.update(image_width=300, image_height=300, unconfirmed_masks=[
            {'xyxy': [163, 209, 180, 216], 'polygon': [[163,209],[180,209],[180,216],[163,216]], 'score': .8},
            {'xyxy': [20,20,30,30], 'polygon': [[20,20],[30,20],[30,30]], 'score': .7}])
        with patch('core.spur_api_assistance.locate_spurs', return_value=self.api):
            result = assist_missed_spurs(self.stream, anatomy, pixels_per_cm=2)
        self.assertEqual(len(result['masks']), 1)
        self.assertEqual(len(result['unconfirmed_masks']), 1)
        self.assertEqual(result['masks'][0]['polygon'], anatomy['unconfirmed_masks'][0]['polygon'])
        self.assertEqual(result['masks'][0]['source'], 'local_segmenter_api_localization')
        self.assertEqual(result['masks'][0]['score'], .8)
        self.assertEqual(len(result['measurements']), 1)
        measurement = result['measurements'][0]
        self.assertEqual(measurement['mask_index'], 0)
        self.assertAlmostEqual(measurement['physical_length_cm'], measurement['length_px']/2, delta=.01)

    def test_api_failure_preserves_existing_local_spurs_masks_and_lengths(self):
        anatomy = copy.deepcopy(self.anatomy)
        anatomy['legs'].append({'xyxy': [40,190,80,245], 'score': .9})
        anatomy['spurs'] = [{'xyxy': [161,205,184,224], 'score': .9}]
        anatomy['masks'] = [{'xyxy': [161,205,184,224], 'polygon': [[161,205],[184,205],[184,224]], 'score': .8}]
        anatomy['measurements'] = [{'length_px': 20, 'mask_index': 0}]
        with patch('core.spur_api_assistance.locate_spurs', return_value={'status':'error','boxes':[]}):
            result = assist_missed_spurs(self.stream, anatomy)
        for key in ('spurs','masks','measurements'):
            self.assertEqual(result[key], anatomy[key])
