import copy
import hashlib
import json
import secrets
import urllib.error
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,Client,override_settings
from django.urls import reverse

from core.models import SpurPredictionCache,SpurCacheCredential,SpurCacheConnection
from core.spur_cache import identity_for,local_prediction,prediction,encrypt_token,decrypt_token,normalized_url


class SpurCacheTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='cache-owner')
        self.other=get_user_model().objects.create_user(username='other-cache-owner')
        self.image=Image.new('RGB',(200,100),'orange')
        self.key,self.identity,_=identity_for(self.image,'localization')
        self.response={'status':'completed','boxes':[[40,10,120,40]],'model':'contract-test','attempts':1,'message':'Recorded contract fixture.'}
        self.token=secrets.token_urlsafe(32)
        SpurCacheCredential.objects.create(user=self.user,token_digest=hashlib.sha256(self.token.encode()).hexdigest())
        self.headers={'HTTP_AUTHORIZATION':'Bearer '+self.token}

    def post_service(self,action,data):
        return self.client.post(reverse('spur_cache_service',args=[action]),json.dumps(data),content_type='application/json',**self.headers)

    def connection(self):
        return SpurCacheConnection.objects.create(user=self.user,service_url='https://smartpoultry-l3qo.onrender.com',
            encrypted_token=encrypt_token(self.token),remote_user_id=9,remote_username='remote-owner')

    def test_pixels_task_and_request_settings_define_identity(self):
        png=BytesIO();self.image.save(png,format='PNG');png.seek(0)
        with Image.open(png) as same:self.assertEqual(identity_for(same,'localization')[0],self.key)
        image=self.image.copy();image.putpixel((0,0),(0,0,0))
        self.assertNotEqual(identity_for(image,'localization')[0],self.key)
        self.assertNotEqual(identity_for(self.image,'geometry')[0],self.key)
        with patch.dict('os.environ',{'GEMINI_SPUR_FALLBACK_MODEL':'another-model'}):
            self.assertNotEqual(identity_for(self.image,'localization')[0],self.key)
        self.assertNotIn('age_months',self.identity);self.assertNotIn('filename',self.identity)

    def test_completed_result_is_persistent_and_does_not_repeat_api_call(self):
        with patch('core.spur_cache._compute',return_value=self.response) as compute:
            first=local_prediction(self.user,self.image,'localization')
            second=local_prediction(self.user,self.image,'localization')
        compute.assert_called_once();self.assertFalse(first['persistent_cache']);self.assertTrue(second['persistent_cache'])
        self.assertEqual(first['boxes'],second['boxes']);self.assertEqual(SpurPredictionCache.objects.count(),1)
        second['boxes'][0][0]=999
        self.assertEqual(SpurPredictionCache.objects.get().response['boxes'][0][0],40)

    def test_failures_never_become_entries_but_successful_empty_predictions_are_valid(self):
        with patch('core.spur_cache._compute',return_value={'status':'error','boxes':[],'message':'HTTP 503'}):
            self.assertEqual(local_prediction(self.user,self.image,'localization')['status'],'error')
        self.assertFalse(SpurPredictionCache.objects.exists())
        with patch('core.spur_cache._compute',return_value={**self.response,'boxes':[]}):local_prediction(self.user,self.image,'localization')
        with patch('core.spur_cache._compute',side_effect=AssertionError('API repeated')):
            self.assertEqual(local_prediction(self.user,self.image,'localization')['boxes'],[])

    def test_concurrent_writer_winner_is_returned_instead_of_losing_api_response(self):
        winner={**self.response,'boxes':[[45,10,121,40]]}
        def competing_write(*args):
            SpurPredictionCache.objects.create(user=self.user,cache_key=self.key,authority='local',
                task='localization',identity=self.identity,response=winner)
            return self.response
        with patch('core.spur_cache._compute',side_effect=competing_write):result=local_prediction(self.user,self.image,'localization')
        self.assertEqual(result['boxes'],winner['boxes']);self.assertEqual(SpurPredictionCache.objects.count(),1)

    def test_users_are_isolated_and_cannot_supply_cache_results(self):
        with patch('core.spur_cache._compute',return_value=self.response):local_prediction(self.user,self.image,'localization')
        self.assertEqual(self.post_service('lookup',{'cache_key':self.key}).json()['boxes'],self.response['boxes'])
        token=secrets.token_urlsafe(32);SpurCacheCredential.objects.create(user=self.other,token_digest=hashlib.sha256(token.encode()).hexdigest())
        self.headers={'HTTP_AUTHORIZATION':'Bearer '+token}
        self.assertEqual(self.post_service('lookup',{'cache_key':self.key}).json()['status'],'miss')
        self.assertEqual(self.post_service('analyze',{'cache_key':self.key,'response':self.response}).status_code,400)

    def test_bearer_required_even_for_signed_in_user_and_revocation_is_immediate(self):
        self.client.force_login(self.user)
        url=reverse('spur_cache_service',args=['identity'])
        self.assertEqual(self.client.post(url).status_code,401)
        self.assertEqual(self.client.get(url,**self.headers).status_code,405)
        self.assertEqual(self.post_service('identity',{}).json()['user_id'],self.user.pk)
        SpurCacheCredential.objects.all().delete()
        self.assertEqual(self.post_service('identity',{}).status_code,401)

    def test_service_recomputes_key_and_only_computes_on_a_miss(self):
        def data(key):
            stream=BytesIO();self.image.save(stream,format='PNG')
            return {'photo':SimpleUploadedFile('pixels.png',stream.getvalue(),content_type='image/png'),'task':'localization','cache_key':key}
        url=reverse('spur_cache_service',args=['analyze'])
        with patch('core.spur_cache._compute',return_value=self.response) as call:
            self.assertEqual(self.client.post(url,data('0'*64),**self.headers).status_code,409)
            call.assert_not_called()
            a=self.client.post(url,data(self.key),**self.headers);b=self.client.post(url,data(self.key),**self.headers)
        call.assert_called_once();self.assertEqual(a.status_code,200);self.assertTrue(b.json()['persistent_cache'])

    def test_pairing_requires_csrf_and_never_stores_plaintext_token(self):
        url=reverse('spur_cache_connection');strict=Client(enforce_csrf_checks=True);strict.force_login(self.user)
        self.assertEqual(strict.post(url,{'action':'issue'}).status_code,403)
        self.client.force_login(self.user)
        with patch('core.spur_cache_service.remote_request',return_value={'user_id':9,'username':'remote-owner'}):
            response=self.client.post(url,{'action':'connect','service_url':'https://smartpoultry-l3qo.onrender.com','service_token':self.token})
        self.assertEqual(response.status_code,200)
        connection=SpurCacheConnection.objects.get();self.assertNotIn(self.token,connection.encrypted_token)
        self.assertEqual(decrypt_token(connection.encrypted_token),self.token)
        self.assertNotContains(response,self.token)
        self.assertIn('no-store',response.headers['Cache-Control'])

    def test_pairing_rotation_is_account_scoped_and_does_not_clear_predictions(self):
        self.client.force_login(self.user)
        response=self.client.post(reverse('spur_cache_connection'),{'action':'issue'})
        token=response.context['issued_token'];self.assertTrue(token);self.assertNotEqual(token,self.token)
        self.assertEqual(self.post_service('identity',{}).status_code,401)
        self.assertEqual(SpurCacheCredential.objects.get(user=self.user).token_digest,hashlib.sha256(token.encode()).hexdigest())

    def test_private_hosts_credentials_queries_and_unsafe_protocol_are_rejected(self):
        for url in ('http://127.0.0.1','https://example.com','https://secret@smartpoultry-l3qo.onrender.com',
                    'https://smartpoultry-l3qo.onrender.com/?token=x','https://smartpoultry-l3qo.onrender.com:444'):
            with self.assertRaises(ValueError):normalized_url(url)

    def test_shared_success_is_persisted_and_used_during_network_outage(self):
        self.connection();shared={**self.response,'cache_key':self.key,'persistent_cache':True}
        with patch('core.spur_cache.remote_request',return_value=shared) as remote,patch('core.spur_cache._compute',side_effect=AssertionError('Desktop called Gemini')):
            result=prediction(self.user,self.image,'localization')
        self.assertTrue(result['shared_cache']);remote.assert_called_once()
        with patch('core.spur_cache.remote_request',side_effect=urllib.error.URLError('offline')):
            again=prediction(self.user,self.image,'localization')
        self.assertEqual(again['boxes'],self.response['boxes']);self.assertTrue(again['persistent_cache'])

    def test_revoked_connection_does_not_use_local_copy_or_call_gemini(self):
        self.connection()
        with patch('core.spur_cache.remote_request',return_value={**self.response,'cache_key':self.key}):prediction(self.user,self.image,'localization')
        with patch('core.spur_cache.remote_request',side_effect=urllib.error.HTTPError('https://service',401,'revoked',{},None)),patch('core.spur_cache._compute') as compute:
            result=prediction(self.user,self.image,'localization')
        self.assertEqual(result['status'],'error');compute.assert_not_called()

    def test_shared_miss_delegates_image_and_never_uploads_a_client_result(self):
        self.connection()
        with patch('core.spur_cache.remote_request',side_effect=[{'status':'miss'},{**self.response,'cache_key':self.key}]) as remote:
            result=prediction(self.user,self.image,'localization')
        self.assertEqual(result['boxes'],self.response['boxes'])
        self.assertEqual(remote.call_args_list[1].args[2],'/api/spur-cache/analyze/')
        body=remote.call_args_list[1].args[3]
        self.assertIn(b'pixels.png',body);self.assertNotIn(b'"response"',body)

    def test_unreachable_unseeded_service_is_error_and_not_a_negative_cache(self):
        self.connection()
        with patch('core.spur_cache.remote_request',side_effect=urllib.error.URLError('offline')),patch('core.spur_cache._compute') as compute:
            result=prediction(self.user,self.image,'localization')
        self.assertEqual(result['status'],'error');self.assertFalse(SpurPredictionCache.objects.exists());compute.assert_not_called()

    def test_geometry_cache_does_not_convert_suggestions_into_measurements(self):
        response={'status':'completed','regions':[{'xyxy':[20,10,180,30],
            'polygon':[[20,10],[180,10],[180,30],[20,30]],'base':None,'tip':[180,20]}],'model':'test-geometry'}
        with patch('core.spur_cache._compute',return_value=response):result=local_prediction(self.user,self.image,'geometry')
        self.assertIsNone(result['regions'][0]['base']);self.assertNotIn('length_px',result)
