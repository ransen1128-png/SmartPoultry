"""Owner-protected review of a visible spur's outline, base, tip and scale."""
import copy
import hashlib
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core import signing
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import RoosterAgeEstimate
from .spur_measurement import measure_visible_spur, _point


@login_required(login_url='login')
@require_http_methods(['GET','POST'])
def review_spur(request, estimate_id):
    record=get_object_or_404(RoosterAgeEstimate,pk=estimate_id,user=request.user)
    if not record.photo:
        raise Http404('Photograph not found.')
    try:
        with record.photo.open('rb') as stream:
            checksum=hashlib.sha256()
            for block in iter(lambda:stream.read(1024*1024),b''):checksum.update(block)
            stream.seek(0)
            with Image.open(stream) as raw:
                from .free_inference import check_image_size
                check_image_size(raw)
                width,height=ImageOps.exif_transpose(raw).size
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):
        messages.error(request,'This photograph cannot be opened for measurement. Use a readable image up to 16 megapixels.')
        return redirect(reverse('rooster_age_estimator')+f'?estimate={record.pk}#latest-results')
    analysis=record.analysis or {}
    previous=analysis.get('spur_review') or {}
    initial=copy.deepcopy(previous.get('measurement') or {})
    if not initial:
        masks=(analysis.get('anatomy') or {}).get('masks') or []
        initial={'polygon':masks[0]['polygon'] if masks else [],'base':None,'tip':None}
    error=None
    from .endpoint_suggestions import candidate_manifest, suggest_geometry
    candidates_available=candidate_manifest() is not None
    from .vision_api import is_configured
    api_available=is_configured()
    api_suggest=request.method=='POST' and request.POST.get('action')=='api_suggest'
    suggestion=None
    draft_token=''
    provenance=None
    if request.method=='GET' and request.GET.get('suggest')=='1' and candidates_available:
        with record.photo.open('rb') as stream:suggestion=suggest_geometry(stream,analysis.get('anatomy') or {})
        if suggestion.get('status')=='draft':
            initial={key:suggestion[key] for key in ('polygon','base','tip')}
            provenance={'source':'endpoint_candidate','model_hashes':suggestion['model_hashes']}
    if api_suggest:
        if request.POST.get('source_sha256')!=checksum.hexdigest():
            suggestion={'status':'error','message':'The photograph changed. Reopen the review before requesting suggestions.'}
        elif not api_available:
            suggestion={'status':'error','message':'Gemini geometry suggestions are not configured.'}
        else:
            from .geometry_api import propose_geometry
            with record.photo.open('rb') as stream:
                with Image.open(stream) as image:response=propose_geometry(image)
            suggestion=response
            if response.get('status')=='completed' and response.get('regions'):
                from .poultry_vision import _box_iou
                references=[p['xyxy'] for p in (analysis.get('anatomy') or {}).get('spurs',[])]
                def rank(region):
                    return max((_box_iou(region['xyxy'],box) for box in references),default=0)
                region=max(response['regions'],key=rank)
                if references and rank(region)<.1:
                    suggestion={'status':'no_matching_geometry','message':'The API outline did not match the existing spur region. Manual marking remains available.'}
                else:
                    initial={key:region[key] for key in ('polygon','base','tip')}
                    provenance={'source':'gemini_api_draft','model':response.get('model'),'prompt_sha256':response.get('prompt_sha256')}
            elif response.get('status')=='completed':
                suggestion={'status':'no_geometry','message':'The API did not return a usable spur outline. Manual marking remains available.'}
    if provenance:
        draft_token=signing.dumps({**provenance,'estimate_id':record.pk,'user_id':request.user.pk,
                                   'image_sha256':checksum.hexdigest()},salt='spur-review-draft',compress=True)
    if request.method=='POST' and not api_suggest:
        try:
            raw=request.POST.get('review_data','')
            if len(raw)>30000:raise ValueError('The review contains too many points.')
            payload=json.loads(raw)
            if not isinstance(payload,dict):raise ValueError('Invalid review document.')
            polygon=payload.get('polygon')
            if not isinstance(polygon,list) or not 3<=len(polygon)<=240:
                raise ValueError('Trace 3 to 240 visible outline points.')
            initial={'polygon':[_point(p,width,height) for p in polygon],
                     'base':_point(payload.get('base'),width,height),'tip':_point(payload.get('tip'),width,height)}
            if request.POST.get('source_sha256')!=checksum.hexdigest():
                raise ValueError('The photograph changed. Reopen this review before saving coordinates.')
            if request.POST.get('visible_confirmation')!='on':
                raise ValueError('Confirm that the outline, base and tip are visible before saving.')
            scale=request.POST.get('pixels_per_cm','').strip() or None
            measured=measure_visible_spur(payload.get('polygon'),payload.get('base'),payload.get('tip'),width,height,scale)
            provenance=None
            token=request.POST.get('draft_token','')
            if token:
                try:provenance=signing.loads(token,salt='spur-review-draft',max_age=86400)
                except signing.BadSignature:raise ValueError('Draft provenance expired or could not be verified. Reopen the review.')
                if (provenance.get('estimate_id')!=record.pk or provenance.get('user_id')!=request.user.pk
                        or provenance.get('image_sha256')!=checksum.hexdigest()):
                    raise ValueError('The draft does not belong to this photograph and account.')
                draft_token=token
            event={'schema_version':1,'source':'user_reviewed','reviewer_user_id':request.user.pk,
                   'created_at':timezone.now().isoformat(),'image_sha256':checksum.hexdigest(),
                   'image_width':width,'image_height':height,'measurement':measured,
                   'draft_provenance':provenance,
                   'training_consent':False,'independent_expert_verification':False}
            with transaction.atomic():
                locked=get_object_or_404(RoosterAgeEstimate.objects.select_for_update(),pk=record.pk,user=request.user)
                saved=copy.deepcopy(locked.analysis or {})
                history=saved.setdefault('spur_review_history',[])
                if len(history)>=100:raise ValueError('This analysis has reached its review history limit.')
                history.append(event);saved['spur_review']=event
                locked.analysis=saved;locked.save(update_fields=['analysis'])
            messages.success(request,'Saved the user-reviewed base, tip and curved pixel measurement. Model predictions and age were preserved.')
            return redirect(reverse('rooster_age_estimator')+f'?estimate={record.pk}#latest-results')
        except (ValueError,TypeError,KeyError,RecursionError) as problem:
            error=str(problem) if not isinstance(problem,json.JSONDecodeError) else 'The review could not be read. Trace the outline and mark both endpoints.'
    return render(request,'spur_measurement_review.html',{'record':record,'width':width,'height':height,
                  'initial':initial,'error':error,'photo_url':reverse('rooster_estimate_photo',args=[record.pk]),
                  'photo_sha256':checksum.hexdigest(),
                  'initial_scale':request.POST.get('pixels_per_cm','') if request.method=='POST' and not api_suggest else
                     (previous.get('measurement',{}).get('calibration',{}).get('pixels_per_cm') or analysis.get('supplied_pixels_per_cm') or ''),
                  'candidates_available':candidates_available,'suggestion':suggestion,'draft_token':draft_token,'api_available':api_available,
                  'back_url':reverse('rooster_age_estimator')+f'?estimate={record.pk}#latest-results'},status=400 if error else 200)
