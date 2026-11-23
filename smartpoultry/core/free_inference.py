"""CPU ONNX inference without importing PyTorch, Transformers or Ultralytics.

Uses FP32 exports of the existing checkpoints. OWL-ViT runs in sequential stages
to bound resident weights without quantization. Original checkpoints are never modified.
YOLO geometry follows Ultralytics 8.3.221 (AGPL-3.0) postprocessing conventions.
"""
import gc,hashlib,importlib.util,json,logging,math,os,threading
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[2]
MODELS=ROOT/'ml_models/free_runtime'
LOCK=threading.RLock()
logger=logging.getLogger(__name__)
MAX_IMAGE_PIXELS=16_000_000
CHICKEN_STAGES=tuple(f'chicken.fp32.stage{i}.onnx' for i in range(5))


def model_assets(task):
    return CHICKEN_STAGES if task=='chicken' else (task+'.onnx',)


def check_image_size(image):
    if image.width*image.height>MAX_IMAGE_PIXELS or max(image.size)>8000:
        raise ValueError('Resize the photo to 16 megapixels or less, with no side larger than 8000 pixels.')


def enabled():
    choice=os.environ.get('SMARTPOULTRY_INFERENCE_RUNTIME','').lower()
    return choice=='onnx' or (not choice and bool(os.environ.get('RENDER') or os.environ.get('RENDER_EXTERNAL_HOSTNAME')))


@lru_cache(maxsize=8)
def manifest():return json.loads((MODELS/'manifest.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=32)
def verified_file(name):
    entry=next(entry for entry in manifest()['files'] if entry['filename']==name)
    path=(MODELS/name).resolve()
    if path.parent!=MODELS.resolve():raise ValueError('Invalid ONNX asset path')
    checksum=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):checksum.update(block)
    if path.stat().st_size!=entry['bytes'] or checksum.hexdigest()!=entry['sha256']:raise ValueError('ONNX asset integrity check failed: '+name)
    return path


@lru_cache(maxsize=8)
def metadata(name):return json.loads(verified_file(name+'.json').read_text(encoding='utf-8'))


def model_files_present(task):
    return all((MODELS/file).is_file() for file in model_assets(task)) and (task not in ('age','chicken') or (MODELS/(task+'.json')).is_file())


def ready(task):
    try:
        for file in model_assets(task):verified_file(file)
        if task in ('age','chicken'):verified_file(task+'.json')
        return importlib.util.find_spec('onnxruntime') is not None
    except (OSError,ValueError,KeyError,StopIteration):return False


def run(task,pixels):
    # One live session at a time prevents model weights/activation arenas from
    # accumulating across requests on the 512 MiB hosted worker.
    import onnxruntime as ort
    with LOCK:
        for file in model_assets(task):
            options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
            options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
            options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
            session=ort.InferenceSession(str(verified_file(file)),sess_options=options,providers=['CPUExecutionProvider'])
            try:outputs=session.run(None,{session.get_inputs()[0].name:np.ascontiguousarray(pixels,dtype=np.float32)})
            finally:
                del session
                gc.collect()
                if os.name=='posix':
                    try:
                        import ctypes
                        ctypes.CDLL(None).malloc_trim(0)
                    except (AttributeError,OSError):pass
            pixels=outputs[0]
        return outputs


def age_ready(variant='finetuned'):
    try:return ready('age') and metadata('age')['model_variant']==variant
    except (OSError,ValueError,KeyError):return False


def predict_age(source,model_variant='finetuned'):
    if not age_ready(model_variant):return None
    meta=metadata('age')
    try:
        source.seek(0)
        with Image.open(source) as image:
            check_image_size(image)
            image=image.convert('RGB').resize((meta['image_size'],)*2,Image.Resampling.BILINEAR)
            pixels=np.asarray(image,dtype=np.float32).transpose(2,0,1)/255.
        pixels=(pixels-np.asarray(meta['mean'],dtype=np.float32)[:,None,None])/np.asarray(meta['std'],dtype=np.float32)[:,None,None]
        value=float(run('age',pixels[None])[0].reshape(-1)[0])
        if not math.isfinite(value):return None
        value=round(max(meta['age_min'],min(meta['age_max'],value)),1)
        return {'age_months':value,'age_range':f'{value} months','test_mae_months':meta['test_mae'],'model_sha256':meta['sha256'],
                'evaluation_status':meta['evaluation_status'],'model_variant':meta['model_variant'],'comparison_metrics':meta['comparison_metrics'],'runtime':'onnx-fp32'}
    except Exception:
        logger.exception('ONNX age inference failed');return None
    finally:source.seek(0)


def nms(boxes,scores,threshold,limit,classes=None):
    order=np.argsort(-scores,kind='stable');keep=[]
    while len(order) and len(keep)<limit:
        i=int(order[0]);keep.append(i);other=order[1:]
        if not len(other):break
        minimum=np.maximum(boxes[i,:2],boxes[other,:2]);maximum=np.minimum(boxes[i,2:],boxes[other,2:])
        intersection=np.prod(np.maximum(maximum-minimum,0),axis=1)
        area=np.prod(np.maximum(boxes[:,2:]-boxes[:,:2],0),axis=1)
        overlap=intersection/np.maximum(area[i]+area[other]-intersection,1e-9)
        if classes is not None:overlap=np.where(classes[other]==classes[i],overlap,0)
        order=other[overlap<=threshold]
    return np.asarray(keep,dtype=int)


def xyxy(values):
    output=values.copy();output[:,:2]=values[:,:2]-values[:,2:]/2;output[:,2:]=values[:,:2]+values[:,2:]/2
    return output


def detect_chicken(source):
    result={'status':'unavailable','boxes':[],'message':'Chicken detection model is unavailable.'}
    if not ready('chicken'):return result
    try:
        meta=metadata('chicken');settings=meta['image_processor'];source.seek(0)
        with Image.open(source) as raw:
            check_image_size(raw)
            image=ImageOps.exif_transpose(raw).convert('RGB');width,height=image.size
            scaled=image.resize((settings['size']['width'],settings['size']['height']),Image.Resampling(settings['resample']))
            pixels=(np.asarray(scaled).astype(np.float64)*settings['rescale_factor']).astype(np.float32)
        pixels=(pixels-np.asarray(settings['image_mean'],dtype=np.float32))/np.asarray(settings['image_std'],dtype=np.float32)
        logits,boxes=run('chicken',pixels.transpose(2,0,1)[None]);labels=logits[0].argmax(axis=-1)
        scores=1/(1+np.exp(-np.clip(logits[0].max(axis=-1),-80,80)))
        chosen=scores>.25;boxes=xyxy(boxes[0][chosen])*np.array([width,height,width,height]);scores=scores[chosen];labels=labels[chosen]
        boxes[:,[0,2]]=boxes[:,[0,2]].clip(0,width);boxes[:,[1,3]]=boxes[:,[1,3]].clip(0,height)
        valid=(boxes[:,2]>boxes[:,0])&(boxes[:,3]>boxes[:,1]);boxes,scores,labels=boxes[valid],scores[valid],labels[valid]
        selected=nms(boxes,scores,.35,4)
        found=[{'xyxy':[round(float(v),1) for v in boxes[i]],'score':round(float(scores[i]),4),'query':meta['queries'][int(labels[i])]} for i in selected]
        status='detected' if any(box['score']>=.35 for box in found) else 'candidate' if found else 'not_detected'
        result.update(status=status,boxes=found,image_width=width,image_height=height,queries=meta['queries'],candidate_threshold=.25,detection_threshold=.35,
                      runtime='onnx-fp32-staged',message='; '.join(f"Box {b['xyxy']} pixels; detector score {b['score']:.3f}; query: {b['query']}" for b in found) if found else 'No chicken body candidate above the 0.25 threshold. This does not prove absence.')
    except Exception:logger.exception('ONNX chicken detection failed');result.update(status='error',message='Chicken detection failed for this image.')
    finally:source.seek(0)
    return result


def letterbox(image):
    import cv2
    width,height=image.size;gain=min(512/height,512/width)
    size=(round(width*gain),round(height*gain));dw=((512-size[0])%32)/2;dh=((512-size[1])%32)/2
    array=np.asarray(image);array=cv2.resize(array,size,interpolation=cv2.INTER_LINEAR) if size!=(width,height) else array
    left,top=round(dw-.1),round(dh-.1)
    array=cv2.copyMakeBorder(array,top,round(dh+.1),left,round(dw+.1),cv2.BORDER_CONSTANT,value=(114,114,114))
    return array.transpose(2,0,1)[None].astype(np.float32)/255.,gain,left,top


def detections(task,pixels,threshold,max_det,gain,left,top,width,height):
    outputs=run(task,pixels);pred=outputs[0][0].T;classes=2 if task=='detect' else 1
    labels=pred[:,4:4+classes].argmax(axis=1);scores=pred[:,4:4+classes].max(axis=1);selected=scores>threshold
    pred,scores,labels=pred[selected],scores[selected],labels[selected]
    boxes=xyxy(pred[:,:4]);chosen=nms(boxes,scores,.45,max_det,labels)
    boxes,scores,labels,pred=boxes[chosen],scores[chosen],labels[chosen],pred[chosen]
    boxes[:,[0,2]]=(boxes[:,[0,2]]-left)/gain;boxes[:,[1,3]]=(boxes[:,[1,3]]-top)/gain
    boxes[:,[0,2]]=boxes[:,[0,2]].clip(0,width);boxes[:,[1,3]]=boxes[:,[1,3]].clip(0,height)
    return boxes,scores,labels,pred[:,4+classes:],outputs[1][0] if task=='segment' else None


def merge_segments(segments):
    # Ultralytics merge_multi_segment: preserve its nearest-point contour joins.
    segments=[np.asarray(s).reshape(-1,2) for s in segments];indexes=[[] for _ in segments];output=[]
    for i in range(1,len(segments)):
        best=None
        # Bound the distance workspace instead of allocating an entire N x M
        # matrix for high-resolution contours. Tuple ordering preserves ties.
        for first in range(0,len(segments[i-1]),32):
            for second in range(0,len(segments[i]),4096):
                distance=((segments[i-1][first:first+32,None]-segments[i][None,second:second+4096])**2).sum(-1)
                a,b=np.unravel_index(np.argmin(distance),distance.shape)
                candidate=(distance[a,b],first+int(a),second+int(b))
                if best is None or candidate<best:best=candidate
        _,a,b=best;indexes[i-1].append(a);indexes[i].append(b)
    for turn in range(2):
        if turn==0:
            for i,idx in enumerate(indexes):
                if len(idx)==2 and idx[0]>idx[1]:idx=idx[::-1];segments[i]=segments[i][::-1]
                segments[i]=np.roll(segments[i],-idx[0],axis=0);segments[i]=np.concatenate([segments[i],segments[i][:1]])
                output.append(segments[i] if i in (0,len(indexes)-1) else segments[i][:idx[1]-idx[0]+1])
        else:
            for i in range(len(indexes)-1,-1,-1):
                if i not in (0,len(indexes)-1):output.append(segments[i][abs(indexes[i][1]-indexes[i][0]):])
    return np.concatenate(output)


def mask_polygons(prototypes,coefficients,boxes,width,height):
    import cv2
    channels,mh,mw=prototypes.shape;gain=min(mh/height,mw/width)
    pw=(mw-width*gain)/2;ph=(mh-height*gain)/2
    left,top=round(pw-.1),round(ph-.1);right,bottom=mw-round(pw+.1),mh-round(ph+.1)
    masks=(coefficients@prototypes.reshape(channels,-1)).reshape(-1,mh,mw)
    polygons=[]
    for mask,box in zip(masks,boxes):
        mask=cv2.resize(mask[top:bottom,left:right],(width,height),interpolation=cv2.INTER_LINEAR)
        x1,y1,x2,y2=np.rint(box).astype(int);mask[:y1]=0;mask[y2:]=0;mask[:,:x1]=0;mask[:,x2:]=0
        contours=cv2.findContours((mask>0).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]
        polygon=merge_segments(contours) if len(contours)>1 else contours[0].reshape(-1,2) if contours else np.zeros((0,2))
        polygons.append(polygon.astype(np.float32))
    return polygons


def analyze_anatomy(source,pixels_per_cm=None,*,detection_only=False):
    from core.poultry_vision import _box_iou,_centerline_measurement
    result={'status':'unavailable','legs':[],'spurs':[],'masks':[],'unconfirmed_masks':[],'measurements':[],
            'image_width':None,'image_height':None,'message':'Anatomy models are unavailable.'}
    if not all(ready(task) for task in (('detect',) if detection_only else ('detect','segment'))):return result
    try:
        if pixels_per_cm is not None and (not math.isfinite(float(pixels_per_cm)) or float(pixels_per_cm)<=0):raise ValueError('Invalid calibration')
        source.seek(0)
        with Image.open(source) as raw:
            check_image_size(raw);image=ImageOps.exif_transpose(raw).convert('RGB')
        width,height=image.size;pixels,gain,left,top=letterbox(image)
        manifest=json.loads((ROOT/'ml_models/poultry_vision/manifest.json').read_text())
        boxes,scores,labels,_,_=detections('detect',pixels,manifest['detect']['threshold'],12,gain,left,top,width,height)
        for box,score,label in zip(boxes,scores,labels):result['legs' if label==0 else 'spurs'].append({'xyxy':[round(float(v),1) for v in box],'score':round(float(score),4),'source':'experimental_detector'})
        if not detection_only:
            boxes,scores,labels,coeff,prototypes=detections('segment',pixels,manifest['segment']['threshold'],6,gain,left,top,width,height)
            for polygon,score in zip(mask_polygons(prototypes,coeff,boxes,width,height),scores):
                if len(polygon)<3:continue
                if len(polygon)>240:polygon=polygon[::math.ceil(len(polygon)/240)]
                polygon[:,0]=polygon[:,0].clip(0,width-1);polygon[:,1]=polygon[:,1].clip(0,height-1)
                points=[[round(float(x),1),round(float(y),1)] for x,y in polygon]
                mask={'polygon':points,'score':round(float(score),4),'xyxy':[round(float(v),1) for v in [*polygon.min(0),*polygon.max(0)]]}
                overlaps=[_box_iou(mask['xyxy'],box['xyxy']) for box in result['spurs']]
                if not overlaps or max(overlaps)<.15:result['unconfirmed_masks'].append(mask);continue
                mask['matched_detector_box']=int(np.argmax(overlaps));result['masks'].append(mask)
                measured=_centerline_measurement(points,width,height,pixels_per_cm)
                if measured:measured['mask_index']=len(result['masks'])-1;result['measurements'].append(measured)
        result.update(status='completed',image_width=width,image_height=height,model_version=manifest['version'],runtime='onnx-fp32',
                      model_provenance={key:{'sha256':manifest[key]['sha256'],'metrics':manifest[key].get('metrics')} for key in ('detect','segment')})
        result['message']=f"Experimental models found {len(result['legs'])} leg candidate(s), {len(result['spurs'])} spur box(es) and {len(result['masks'])} spur mask(s). {len(result['unconfirmed_masks'])} outline proposal(s) lacked matching spur boxes. No detection above threshold does not establish anatomical absence."
    except Exception:logger.exception('ONNX anatomy inference failed');result.update(status='error',message='Anatomy inference failed for this image.')
    finally:source.seek(0)
    return result
