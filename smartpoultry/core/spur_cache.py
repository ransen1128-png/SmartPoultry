"""Account-scoped, immutable successful API predictions and authenticated sharing."""
import base64
import copy
import hashlib
import json
import math
from io import BytesIO
from urllib.parse import urlsplit
import urllib.error
import urllib.request

from django.conf import settings
from PIL import ImageOps, __version__ as pillow_version


def identity_for(image, task):
    from .free_inference import check_image_size
    from .vision_api import PROMPT_HASH, REQUEST_POLICY_HASH, spur_model, spur_backup_model
    from .geometry_api import PROMPT_HASH as geometry_prompt
    check_image_size(image)
    if task not in ('localization','geometry'):raise ValueError('Unknown prediction task.')
    rgb=image if image.mode=='RGB' and image.getexif().get(274,1)==1 else ImageOps.exif_transpose(image).convert('RGB')
    pixels=hashlib.sha256()
    # Stream rows to avoid another full-image byte buffer on a 512 MB worker.
    for y in range(0,rgb.height,128):pixels.update(rgb.crop((0,y,rgb.width,min(y+128,rgb.height))).tobytes())
    identity={'schema':1,'task':task,'width':rgb.width,'height':rgb.height,
              'pixels_sha256':pixels.hexdigest(),
              'primary_model':spur_model(),'backup_model':spur_backup_model() if task=='localization' else '',
              'prompt_sha256':PROMPT_HASH if task=='localization' else geometry_prompt,
              'request_policy_sha256':REQUEST_POLICY_HASH,'image_policy':'exif-rgb;max1024;jpeg92',
              'pillow':pillow_version,'temperature':0,'thinking':'gemini3-low',
              'max_output_tokens':2048 if task=='localization' else 4096,
              'attempt_policy':'primary2-backup1-20seconds' if task=='localization' else 'primary1-20seconds'}
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return key,identity,rgb


def validated_response(response,identity):
    if not isinstance(response,dict) or response.get('status')!='completed':raise ValueError('Only completed API responses can be cached.')
    if len(json.dumps(response,allow_nan=False))>200000:raise ValueError('Prediction exceeds cache size limit.')
    width,height=identity['width'],identity['height']
    def box(b):
        if (not isinstance(b,list) or len(b)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in b)
            or not 0<=b[0]<b[2]<=width or not 0<=b[1]<b[3]<=height):raise ValueError('Invalid cached box.')
    if identity['task']=='localization':
        boxes=response.get('boxes')
        if not isinstance(boxes,list) or len(boxes)>4:raise ValueError('Invalid cached boxes.')
        for b in boxes:box(b)
    else:
        from .spur_measurement import validate_outline,_point
        regions=response.get('regions')
        if not isinstance(regions,list) or len(regions)>4:raise ValueError('Invalid cached geometry.')
        for r in regions:
            box(r['xyxy']);validate_outline(r['polygon'],width,height)
            for k in ('base','tip'):
                if r.get(k) is not None:_point(r[k],width,height)
    result=copy.deepcopy(response)
    for k in ('persistent_cache','shared_cache','cache_key','cache_created_at'):result.pop(k,None)
    return result


def _from_row(row,hit=True,shared=False):
    result=validated_response(row.response,row.identity)
    result.update(cached=hit,persistent_cache=hit,shared_cache=shared,cache_key=row.cache_key,
                  cache_created_at=row.created_at.isoformat())
    return result


def _compute(image,task):
    if task=='localization':
        from .vision_api import locate_spurs_with_fallback
        return locate_spurs_with_fallback(image)
    from .geometry_api import propose_geometry
    return propose_geometry(image)


def local_prediction(user,image,task):
    """First successful committed response wins concurrent cache misses."""
    from .models import SpurPredictionCache
    key,identity,rgb=identity_for(image,task)
    row=SpurPredictionCache.objects.filter(user=user,cache_key=key,authority='local').first()
    if row:return _from_row(row)
    result=_compute(rgb,task)
    if result.get('status')!='completed':return result
    response=validated_response(result,identity)
    row,created=SpurPredictionCache.objects.get_or_create(user=user,cache_key=key,authority='local',
                                                       defaults={'task':task,'identity':identity,'response':response})
    return _from_row(row,hit=not created)


def normalized_url(value):
    parsed=urlsplit(value.strip())
    allowed=getattr(settings,'SPUR_CACHE_ALLOWED_HOSTS',['smartpoultry-l3qo.onrender.com'])
    test_http=getattr(settings,'SPUR_CACHE_ALLOW_HTTP_TEST_ONLY',False)
    if (parsed.hostname not in allowed or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in ('','/') or parsed.scheme not in (('https','http') if test_http else ('https',))
        or (not test_http and parsed.port not in (None,443))):
        raise ValueError('Use the approved HTTPS SmartPoultry service address.')
    return f'{parsed.scheme}://{parsed.netloc}'.rstrip('/')


def encrypt_token(token):
    from cryptography.fernet import Fernet
    key=base64.urlsafe_b64encode(hashlib.sha256(('spur-cache:'+settings.SECRET_KEY).encode()).digest())
    return Fernet(key).encrypt(token.encode()).decode()


def decrypt_token(value):
    from cryptography.fernet import Fernet,InvalidToken
    key=base64.urlsafe_b64encode(hashlib.sha256(('spur-cache:'+settings.SECRET_KEY).encode()).digest())
    try:return Fernet(key).decrypt(value.encode()).decode()
    except InvalidToken:raise ValueError('Connection key changed; reconnect the service.')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def remote_request(url,token,path,data,content_type='application/json',timeout=10):
    url=normalized_url(url)
    request=urllib.request.Request(url+path,data=data,headers={'Authorization':'Bearer '+token,'Content-Type':content_type},method='POST')
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=timeout) as response:raw=response.read(200001)
    if len(raw)>200000:raise ValueError('Shared service response exceeds size limit.')
    return json.loads(raw)


def prediction(user,image,task):
    from .models import SpurCacheConnection,SpurPredictionCache
    if getattr(settings,'RUNNING_ON_RENDER',False):return local_prediction(user,image,task)
    connection=SpurCacheConnection.objects.filter(user=user).first()
    if not connection:return local_prediction(user,image,task)
    key,identity,rgb=identity_for(image,task)
    authority=connection.service_url+':'+str(connection.remote_user_id)
    local=SpurPredictionCache.objects.filter(user=user,cache_key=key,authority=authority).first()
    try:
        token=decrypt_token(connection.encrypted_token)
        result=remote_request(connection.service_url,token,'/api/spur-cache/lookup/',json.dumps({'cache_key':key}).encode())
        if result.get('status')=='miss':
            stream=BytesIO();rgb.save(stream,format='PNG')
            # Multipart preserves exact oriented pixels; only the service computes predictions.
            import secrets
            boundary='spur-'+secrets.token_hex(16)
            data=(f'--{boundary}\r\nContent-Disposition: form-data; name="task"\r\n\r\n{task}\r\n'
                  f'--{boundary}\r\nContent-Disposition: form-data; name="cache_key"\r\n\r\n{key}\r\n'
                  f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="pixels.png"\r\nContent-Type: image/png\r\n\r\n').encode()+stream.getvalue()+f'\r\n--{boundary}--\r\n'.encode()
            result=remote_request(connection.service_url,token,'/api/spur-cache/analyze/',data,
                                  f'multipart/form-data; boundary={boundary}',timeout=100)
        if result.get('status')!='completed':return result
        if result.get('cache_key')!=key:raise ValueError('Shared prediction identity does not match.')
        clean=validated_response(result,identity)
        row,_=SpurPredictionCache.objects.get_or_create(user=user,cache_key=key,authority=authority,
                                defaults={'task':task,'identity':identity,'response':clean})
        # The service is authoritative if a local copy from an earlier deployment differs.
        if row.response!=clean:
            row.response=clean;row.save(update_fields=['response'])
        return _from_row(row,hit=result.get('persistent_cache',False),shared=True)
    except urllib.error.HTTPError as error:
        if error.code>=500 and local:return _from_row(local,shared=True)
        return {'status':'error','message':f'Shared cache HTTP {error.code}. Check the connection or service settings.','boxes':[],'regions':[]}
    except (urllib.error.URLError,TimeoutError,OSError):
        if local:return _from_row(local,shared=True)
        return {'status':'error','message':'Shared cache service is unreachable; no successful saved result exists for this image and settings.','boxes':[],'regions':[]}
    except (ValueError,KeyError,TypeError):
        return {'status':'error','message':'Shared cache response or connection could not be verified. Reconnect the service.','boxes':[],'regions':[]}
