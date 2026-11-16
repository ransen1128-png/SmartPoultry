import json
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
from PIL import Image
from core.vision_api import locate_spurs,locate_spurs_with_fallback,validate_boxes,crop_visible_spur,spur_model,is_configured


class VisionAPIContractTests(TestCase):
    def test_overloaded_primary_uses_one_backup_and_preserves_attempt_provenance(self):
        responses=[{'status':'error','http_status':503,'boxes':[],'attempts':2,'message':'Provider overloaded.'},
                   {'status':'completed','boxes':[[40,10,120,40]],'attempts':1,'message':'API prediction.'}]
        with patch.dict('os.environ',{'GEMINI_SPUR_BACKUP_MODEL':'backup-test'}),patch('core.vision_api.locate_spurs',side_effect=responses) as call:
            result=locate_spurs_with_fallback(Image.new('RGB',(200,100)),model='primary-test')
        self.assertEqual(call.call_count,2)
        self.assertEqual(call.call_args.kwargs,{'model':'backup-test','timeout':20,'max_attempts':1})
        self.assertEqual(result['model'],'backup-test')
        self.assertEqual(result['attempts'],3)
        self.assertEqual(result['boxes'],[[40,10,120,40]])
        self.assertEqual(result['model_attempts'][0]['http_status'],503)
        self.assertTrue(result['fallback_used'])

    def test_no_failover_for_successful_empty_response_key_quota_or_invalid_response(self):
        responses=[{'status':'completed','boxes':[],'attempts':1},
                   {'status':'error','http_status':403,'boxes':[],'attempts':1},
                   {'status':'error','http_status':429,'boxes':[],'attempts':1},
                   {'status':'error','boxes':[],'attempts':1}]
        for response in responses:
            with patch('core.vision_api.locate_spurs',return_value=response) as call:
                result=locate_spurs_with_fallback(Image.new('RGB',(201,101)))
            call.assert_called_once()
            self.assertFalse(result['fallback_used'])
            self.assertEqual(result['boxes'],[])

    def test_failover_exhaustion_retains_errors_and_never_fabricates_detection(self):
        responses=[{'status':'error','error_kind':'network','boxes':[],'attempts':2,'message':'Timeout.'},
                   {'status':'error','http_status':503,'boxes':[],'attempts':1,'message':'Provider overloaded.'}]
        with patch.dict('os.environ',{'GEMINI_SPUR_BACKUP_MODEL':'backup-test'}),patch('core.vision_api.locate_spurs',side_effect=responses):
            result=locate_spurs_with_fallback(Image.new('RGB',(202,102)),model='primary-test')
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['boxes'],[])
        self.assertEqual(len(result['model_attempts']),2)
        self.assertEqual(result['attempts'],3)

    def test_spur_model_default_and_explicit_override_do_not_use_legacy_benchmark_model(self):
        with patch.dict('os.environ',{'GEMINI_API_KEY':'configuration-test','GEMINI_VISION_MODEL':'legacy',
                                     'GEMINI_SPUR_FALLBACK_MODEL':''}):
            self.assertEqual(spur_model(),'gemini-3.1-flash-lite')
            self.assertTrue(is_configured())
        with patch.dict('os.environ',{'GEMINI_SPUR_FALLBACK_MODEL':' explicit-test-model '}):
            self.assertEqual(spur_model(),'explicit-test-model')

    def test_temporary_network_failure_retries_without_fabricating_boxes(self):
        response={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"boxes": [[100,200,400,600]]}'}]}}]}
        with patch('core.vision_api.urllib.request.urlopen',side_effect=[TimeoutError(),BytesIO(json.dumps(response).encode())]) as call,patch('core.vision_api.time.sleep'):
            result=locate_spurs(Image.new('RGB',(201,101)),api_key='retry-contract-key',model='retry-test-model',max_attempts=2)
        self.assertEqual(call.call_count,2)
        self.assertEqual(result['attempts'],2)
        self.assertEqual(result['status'],'completed')

    def test_gemini3_requests_use_bounded_thinking_and_record_policy(self):
        response={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"boxes": []}'}]}}]}
        with patch('core.vision_api.urllib.request.urlopen',return_value=BytesIO(json.dumps(response).encode())) as request:
            result=locate_spurs(Image.new('RGB',(110,90)),api_key='policy-contract-key',model='gemini-3.1-flash-lite')
        self.assertEqual(result['status'],'completed')
        body=json.loads(request.call_args.args[0].data)
        self.assertEqual(body['generationConfig']['thinkingConfig'],{'thinkingLevel':'low'})
        self.assertIn('request_policy_sha256',result)

    def test_coordinates_are_validated_and_scaled_to_original_image(self):
        self.assertEqual(validate_boxes({'boxes':[[100,200,400,600]]},200,100),[[40,10,120,40]])
        for payload in ({'boxes':[[0,0,float('nan'),900]]},{'boxes':[[0,0,0,900]]},{'boxes':[[False,0,900,900]]},{'boxes':[[0,0,1001,900]]},{}):
            with self.assertRaises(ValueError):validate_boxes(payload,200,100)

    def test_missing_configuration_does_not_make_a_network_call(self):
        with patch.dict('os.environ',{},clear=True),patch('core.vision_api.urllib.request.urlopen') as request:
            result=locate_spurs(Image.new('RGB',(100,100)))
        self.assertEqual(result['status'],'unconfigured');request.assert_not_called()

    def test_no_box_never_invents_a_crop_or_measurement(self):
        self.assertIsNone(crop_visible_spur(Image.new('RGB',(100,100)),[]))

    def test_request_sends_image_pixels_without_age_labels_and_validates_response(self):
        response={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'boxes':[[100,200,400,600]]})}]}}],'modelVersion':'contract-test'}
        with patch('core.vision_api.urllib.request.urlopen',return_value=BytesIO(json.dumps(response).encode())) as request:
            result=locate_spurs(Image.new('RGB',(200,100)),api_key='private-test-key',model='test-model')
        self.assertEqual(result['status'],'completed');self.assertEqual(result['boxes'],[[40,10,120,40]])
        sent=request.call_args.args[0]
        self.assertNotIn('private-test-key',sent.full_url)
        self.assertIn('inlineData',json.loads(sent.data)['contents'][0]['parts'][1])
        self.assertNotIn('age_months',sent.data.decode())

    def test_truncated_or_blocked_response_does_not_report_detection(self):
        response={'candidates':[{'finishReason':'MAX_TOKENS'}]}
        with patch('core.vision_api.urllib.request.urlopen',return_value=BytesIO(json.dumps(response).encode())):
            result=locate_spurs(Image.new('RGB',(100,100)),api_key='test',model='test-model')
        self.assertEqual(result['status'],'error');self.assertEqual(result['boxes'],[])

    def test_crop_padding_stays_inside_image(self):
        image=Image.new('RGB',(200,100))
        self.assertEqual(crop_visible_spur(image,[[0,0,200,100]]).size,image.size)
