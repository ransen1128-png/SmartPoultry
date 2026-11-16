"""Local review-only suggestions from separately trained endpoint/outline models."""
import hashlib
import json
import os
import threading
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'ml_models/spur_measurement/candidates.json'
LOCK=threading.RLock()


def candidate_manifest():
    if os.environ.get('RENDER') or os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
        return None
    try:
        document=json.loads(MANIFEST.read_text())
        if document.get('purpose')!='review_suggestions_only':return None
        for task in ('pose','segment'):
            path=(ROOT/document[task]['filename']).resolve()
            allowed=path.is_relative_to((ROOT/'detection/runs').resolve())
            if task=='segment':allowed |= path.is_relative_to((ROOT/'ml_models/poultry_vision').resolve())
            if not allowed or not path.is_file():return None
        return document
    except (OSError,ValueError,KeyError,TypeError):return None


@lru_cache(maxsize=2)
def _models(text):
    from ultralytics import YOLO
    from .ml_runtime import configure_cpu_runtime
    configure_cpu_runtime()
    document=json.loads(text);models={}
    for task in ('pose','segment'):
        path=(ROOT/document[task]['filename']).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest()!=document[task]['sha256']:
            raise ValueError('Candidate checkpoint integrity check failed.')
        models[task]=YOLO(str(path))
        if models[task].names!={0:'spur'}:raise ValueError('Unexpected candidate class labels.')
    if list(models['pose'].model.model[-1].kpt_shape)!=[2,3]:
        raise ValueError('Endpoint model must predict base and tip with visibility.')
    return models


def suggest_geometry(photo, anatomy):
    document=candidate_manifest()
    if not document:return {'status':'unavailable','message':'Endpoint candidates are not configured for this server.'}
    try:
        models=_models(json.dumps(document,sort_keys=True))
        photo.seek(0)
        with Image.open(photo) as raw:
            from .free_inference import check_image_size
            check_image_size(raw);image=ImageOps.exif_transpose(raw).convert('RGB')
        with LOCK:
            pose=models['pose'].predict(image,imgsz=512,conf=document['pose']['threshold'],iou=.45,max_det=6,device='cpu',verbose=False)[0]
            segment=models['segment'].predict(image,imgsz=512,conf=document['segment']['threshold'],iou=.45,max_det=6,retina_masks=True,device='cpu',verbose=False)[0]
        from .poultry_vision import _box_iou
        if pose.keypoints is None or segment.masks is None:
            return {'status':'no_complete_geometry','message':'The candidates did not produce both a spur outline and visible base/tip points. You can mark the visible geometry below.'}
        references=[box['xyxy'] for box in anatomy.get('spurs',[])]
        choices=[]
        for pidx,box in enumerate(pose.boxes.xyxy.tolist()):
            if min(pose.keypoints.conf[pidx].tolist())<.5:continue
            if references and max(_box_iou(box,r) for r in references)<.1:continue
            for sidx,sbox in enumerate(segment.boxes.xyxy.tolist()):
                overlap=_box_iou(box,sbox)
                if overlap>=.15:choices.append((overlap*float(pose.boxes.conf[pidx])*float(segment.boxes.conf[sidx]),pidx,sidx))
        if not choices:
            return {'status':'no_complete_geometry','message':'No matching outline and endpoint proposal passed the review-suggestion checks. Mark only the geometry you can see.'}
        _,pidx,sidx=max(choices)
        polygon=segment.masks.xy[sidx].tolist()
        if len(polygon)>240:
            import math
            polygon=polygon[::math.ceil(len(polygon)/240)]
        base,tip=pose.keypoints.xy[pidx].tolist()
        return {'status':'draft','message':'These are candidate model suggestions, not verified endpoints. Correct the outline, base and tip before confirming visibility.',
                'polygon':polygon,'base':base,'tip':tip,
                'model_hashes':{task:document[task]['sha256'] for task in ('pose','segment')}}
    except (OSError,ValueError,RuntimeError,ImportError,TypeError,KeyError):
        return {'status':'error','message':'Candidate suggestions could not be produced. Manual review remains available.'}
    finally:photo.seek(0)
