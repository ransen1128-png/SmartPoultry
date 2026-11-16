"""Bearer-only, owner-scoped cache service and CSRF-protected pairing page."""
import hashlib
import json
import re
import secrets
import urllib.error

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST,require_http_methods
from PIL import Image,ImageOps

from .models import SpurCacheCredential,SpurCacheConnection,SpurPredictionCache
from .spur_cache import identity_for,local_prediction,_from_row,normalized_url,remote_request,encrypt_token


@csrf_exempt
@require_POST
@never_cache
def service(request,action):
    header=request.headers.get('Authorization','')
    token=header[7:] if header.startswith('Bearer ') else ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):return JsonResponse({'status':'unauthorized'},status=401)
    credential=SpurCacheCredential.objects.select_related('user').filter(token_digest=hashlib.sha256(token.encode()).hexdigest(),user__is_active=True).first()
    if not credential:return JsonResponse({'status':'unauthorized'},status=401)
    user=credential.user
    if action=='identity':return JsonResponse({'user_id':user.pk,'username':user.username})
    if action=='lookup':
        try:
            if len(request.body)>1000:raise ValueError()
            key=json.loads(request.body)['cache_key']
            if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):raise ValueError()
        except (ValueError,KeyError,TypeError):return JsonResponse({'status':'error','message':'Invalid cache key.'},status=400)
        row=SpurPredictionCache.objects.filter(user=user,cache_key=key,authority='local').first()
        return JsonResponse(_from_row(row) if row else {'status':'miss'})
    if action!='analyze':return JsonResponse({'status':'error'},status=404)
    photo=request.FILES.get('photo');task=request.POST.get('task');expected=request.POST.get('cache_key')
    if photo is None or photo.size>64*1024*1024:return JsonResponse({'status':'error','message':'Supply a photo up to 64 MB and 16 megapixels.'},status=400)
    try:
        with Image.open(photo) as raw:
            from .free_inference import check_image_size
            check_image_size(raw)
            image=ImageOps.exif_transpose(raw).convert('RGB')
        key,_,_=identity_for(image,task)
        if key!=expected:return JsonResponse({'status':'error','message':'Image or model settings differ from the service. Update both applications to the same version.'},status=409)
        return JsonResponse(local_prediction(user,image,task))
    except (OSError,ValueError,TypeError,Image.DecompressionBombError):
        return JsonResponse({'status':'error','message':'The photo or prediction could not be validated.'},status=400)


@login_required(login_url='login')
@require_http_methods(['GET','POST'])
@never_cache
def connection_page(request):
    connection=SpurCacheConnection.objects.filter(user=request.user).first()
    error=None;issued_token=None;notice=None
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='issue':
            issued_token=secrets.token_urlsafe(32)
            SpurCacheCredential.objects.update_or_create(user=request.user,defaults={'token_digest':hashlib.sha256(issued_token.encode()).hexdigest()})
            notice='Created a service token for your account. Any previous service token is revoked. Copy this token now; it is shown only once.'
        elif action=='revoke':
            SpurCacheCredential.objects.filter(user=request.user).delete();notice='Service token revoked.'
        elif action=='disconnect':
            SpurCacheConnection.objects.filter(user=request.user).delete();connection=None;notice='Disconnected. Local saved predictions are preserved.'
        elif action=='connect':
            try:
                if getattr(settings,'RUNNING_ON_RENDER',False):raise ValueError('Connect from localhost.')
                url=normalized_url(request.POST.get('service_url',''))
                token=request.POST.get('service_token','').strip()
                if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise ValueError('Enter a valid service token from your Render account.')
                owner=remote_request(url,token,'/api/spur-cache/identity/',b'{}')
                if type(owner.get('user_id')) is not int or owner['user_id']<=0 or not isinstance(owner.get('username'),str):raise ValueError('Invalid service identity.')
                connection,_=SpurCacheConnection.objects.update_or_create(user=request.user,defaults={
                    'service_url':url,'encrypted_token':encrypt_token(token),'remote_user_id':owner['user_id'],'remote_username':owner['username'][:150]})
                notice='Connected to the selected Render account. New analyses use its authoritative saved API predictions.'
            except (ValueError,KeyError,TypeError):error='The connection could not be verified. Check the service address and token.'
            except (urllib.error.URLError,TimeoutError,OSError):error='The service could not authenticate the connection. Check the token and retry when the service is available.'
        else:error='Unknown connection action.'
    return render(request,'spur_cache_connection.html',{'connection':connection,'issued_token':issued_token,'error':error,'notice':notice,
                  'default_service_url':'https://smartpoultry-l3qo.onrender.com',
                  'hosted_service':getattr(settings,'RUNNING_ON_RENDER',False),
                  'credential_exists':SpurCacheCredential.objects.filter(user=request.user).exists(),
                  'cache_count':SpurPredictionCache.objects.filter(user=request.user).count()},status=400 if error else 200)
