import json
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
from PIL import Image
from core.vision_api import locate_spurs,validate_boxes,crop_visible_spur


class VisionAPIContractTests(TestCase):
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
