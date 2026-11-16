import copy
import json
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from PIL import Image

from core.geometry_api import propose_geometry, validate_geometry


class GeometryAPIContractTests(TestCase):
    def payload(self):
        return {'regions':[{'box':[100,100,300,900],
                            'polygon':[[100,100],[900,100],[900,300],[100,300]],
                            'base':[100,200],'tip':[900,200]}]}

    def test_real_polygons_and_endpoints_are_scaled_without_measurement_claims(self):
        region=validate_geometry(self.payload(),200,100)[0]
        self.assertEqual(region['base'],[20,20]);self.assertEqual(region['tip'],[180,20])
        self.assertEqual(region['polygon'],[[20,10],[180,10],[180,30],[20,30]])
        self.assertNotIn('length_px',region);self.assertNotIn('physical_length_cm',region)
        payload=self.payload();payload['regions'][0]['base']=None
        self.assertIsNone(validate_geometry(payload,200,100)[0]['base'])

    def test_malformed_or_self_crossing_geometry_is_rejected(self):
        cases=[{'regions':[{}]},{'regions':[self.payload()['regions'][0]]*5}]
        for change in ({'polygon':[[100,100],[900,900],[100,900],[900,100]]},
                       {'base':[False,200]},{'tip':[float('nan'),200]}, {'polygon':[[100,100]]*81}):
            payload=copy.deepcopy(self.payload());payload['regions'][0].update(change);cases.append(payload)
        for payload in cases:
            with self.assertRaises(ValueError):validate_geometry(payload,200,100)

    def test_missing_credentials_never_send_a_photo(self):
        with patch.dict('os.environ',{},clear=True),patch('core.geometry_api.urllib.request.urlopen') as call:
            result=propose_geometry(Image.new('RGB',(200,100)))
        self.assertEqual(result['status'],'unconfigured');call.assert_not_called()

    def test_request_cache_copies_geometry_and_preserves_private_key(self):
        response={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(self.payload())}]}}], 'modelVersion':'geometry-contract'}
        with patch.dict('os.environ',{'GEMINI_API_KEY':'private-geometry-test-key','GEMINI_SPUR_FALLBACK_MODEL':'geometry-contract'}),patch('core.geometry_api.urllib.request.urlopen',return_value=BytesIO(json.dumps(response).encode())) as call:
            first=propose_geometry(Image.new('RGB',(200,100),'orange'))
            self.assertEqual(first['status'],'completed')
            first['regions'][0]['base'][0]=999
            second=propose_geometry(Image.new('RGB',(200,100),'orange'))
        self.assertTrue(second['cached']);self.assertEqual(second['regions'][0]['base'],[20,20])
        call.assert_called_once();request=call.call_args.args[0]
        self.assertNotIn('private-geometry-test-key',request.full_url)
        self.assertNotIn('age_months',request.data.decode())
