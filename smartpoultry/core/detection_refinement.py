"""Bounded, sequential retries on image regions; never fabricate anatomy."""
import copy
import math
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


def _image(source):
    source.seek(0)
    with Image.open(source) as raw:
        from .free_inference import check_image_size
        check_image_size(raw)
        return ImageOps.exif_transpose(raw).convert('RGB')


def _upload(image):
    stream = BytesIO()
    image.save(stream, format='PNG'); stream.seek(0)
    return stream


def _valid(region, minimum=0):
    box, score = region.get('xyxy'), region.get('score')
    return (isinstance(box, (list, tuple)) and len(box) == 4
            and all(type(v) in (float, int) and math.isfinite(v) for v in box)
            and box[2] > box[0] >= 0 and box[3] > box[1] >= 0
            and type(score) in (float, int) and math.isfinite(score) and score >= minimum)


def _iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    return intersection / max(1, (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)


def _same_region(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    smaller = min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1]))
    return _iou(a,b) > .35 or intersection / max(1, smaller) > .65


def _window(box, size, padding):
    x1, y1, x2, y2 = box; width, height = x2-x1, y2-y1
    return (max(0, math.floor(x1-width*padding)), max(0, math.floor(y1-height*padding)),
            min(size[0], math.ceil(x2+width*padding)), min(size[1], math.ceil(y2+height*padding)))


def refine_chicken(source, original, infer):
    """Retry one candidate crop or mirrored view; recovery needs score >= .50."""
    if original.get('status') not in ('candidate', 'not_detected'):
        return original
    try:
        image = _image(source)
        candidates = [box for box in original.get('boxes', []) if _valid(box, .25)]
        crop = _window(max(candidates, key=lambda box:box['score'])['xyxy'], image.size, .25) if candidates else None
        if crop and min(crop[2]-crop[0], crop[3]-crop[1]) < 32:
            crop = None
        retry = infer(_upload(image.crop(crop) if crop else ImageOps.mirror(image)))
        recovered = []
        for region in retry.get('boxes', []):
            if not _valid(region, .5): continue
            box = list(region['xyxy'])
            if crop:
                box = [box[0]+crop[0], box[1]+crop[1], box[2]+crop[0], box[3]+crop[1]]
            else:
                box = [image.width-box[2], box[1], image.width-box[0], box[3]]
            if not (0 <= box[0] < box[2] <= image.width and 0 <= box[1] < box[3] <= image.height): continue
            recovered.append({**region, 'xyxy':box, 'refinement':'candidate_crop' if crop else 'mirrored_view'})
        result = copy.deepcopy(original)
        result['body_refinement'] = {'attempts':1, 'recovered':len(recovered)}
        if recovered:
            result.update(status='detected', boxes=recovered,
                          image_width=image.width, image_height=image.height,
                          message='Chicken body detected on a second view. ' + '; '.join(
                              f"Box {box['xyxy']} pixels; detector score {box['score']:.3f}" for box in recovered))
        return result
    except (OSError, ValueError, RuntimeError, UnidentifiedImageError):
        return original
    finally:
        source.seek(0)


def refine_anatomy(source, detection, original, infer, pixels_per_cm=None, *, detection_only=False):
    """At most two crops, preserving pixels, calibration and original coordinates."""
    if original.get('status') != 'completed': return original
    legs = [box for box in original.get('legs', []) if _valid(box, .75)]
    spurs = [box for box in original.get('spurs', []) if _valid(box, .75)]
    bodies = [box for box in detection.get('boxes', []) if _valid(box, .35)] if detection.get('status') == 'detected' else []
    if not bodies and not any(_valid(box, .85) for box in legs+spurs): return original
    missing_outline = not detection_only and len(original.get('masks', [])) < len(spurs)
    if spurs and not missing_outline and (len(legs) >= 2 or not bodies): return original
    try:
        image = _image(source)
        windows = []
        if missing_outline:
            windows.extend(_window(box['xyxy'], image.size, 1) for box in spurs)
        windows.extend(_window(box['xyxy'], image.size, .65) for box in sorted(legs, key=lambda box:-box['score']))
        for body in bodies[:1]:
            x1, y1, x2, y2 = body['xyxy']
            windows.append(_window([x1, y1+(y2-y1)*.45, x2, y2], image.size, .15))
        selected = []
        for window in windows:
            area = (window[2]-window[0])*(window[3]-window[1])
            if min(window[2]-window[0], window[3]-window[1]) < 24 or area >= image.width*image.height*.85: continue
            if any(_iou(window, old) > .8 for old in selected): continue
            selected.append(window)
            if len(selected) == 2: break
        result = copy.deepcopy(original)
        before = {key:len(result.get(key, [])) for key in ('legs','spurs','masks')}
        for window in selected:
            crop = infer(_upload(image.crop(window)), pixels_per_cm, detection_only=True) if detection_only else infer(_upload(image.crop(window)), pixels_per_cm)
            if crop.get('status') != 'completed': continue
            def translated(region):
                region = copy.deepcopy(region)
                x1, y1, x2, y2 = region['xyxy']
                region['xyxy'] = [x1+window[0], y1+window[1], x2+window[0], y2+window[1]]
                region['refinement'] = 'anatomy_crop'
                if 'polygon' in region:
                    region['polygon'] = [[x+window[0], y+window[1]] for x,y in region['polygon']]
                return region
            for key in ('legs', 'spurs'):
                for region in crop.get(key, []):
                    if not _valid(region, .75): continue
                    # A second detector pass alone can confuse toes with spurs.
                    # New spur regions need an independently predicted outline.
                    if key == 'spurs' and not any(_valid(mask, .75) and _iou(region['xyxy'], mask['xyxy']) >= .15 for mask in crop.get('masks', [])):
                        continue
                    region = translated(region)
                    if bodies:
                        x1,y1,x2,y2 = region['xyxy']; cx,cy = (x1+x2)/2,(y1+y2)/2
                        if not any(b['xyxy'][0] <= cx <= b['xyxy'][2] and b['xyxy'][1] <= cy <= b['xyxy'][3] for b in bodies): continue
                    if any(_same_region(region['xyxy'], old['xyxy']) for old in result[key]): continue
                    result[key].append(region)
            if detection_only: continue
            for index, mask in enumerate(crop.get('masks', [])):
                if not _valid(mask, .75): continue
                mask = translated(mask)
                overlaps = [_iou(mask['xyxy'], box['xyxy']) for box in result['spurs']]
                if not overlaps or max(overlaps) < .15: continue
                if any(_same_region(mask['xyxy'], old['xyxy']) for old in result['masks']): continue
                mask['matched_detector_box'] = overlaps.index(max(overlaps))
                mask_index = len(result['masks']); result['masks'].append(mask)
                for measurement in crop.get('measurements', []):
                    if measurement.get('mask_index') != index: continue
                    measurement = copy.deepcopy(measurement)
                    measurement['mask_index'] = mask_index
                    measurement['centerline'] = [[x+window[0],y+window[1]] for x,y in measurement['centerline']]
                    result['measurements'].append(measurement)
        result['anatomy_refinement'] = {'attempts':len(selected), 'added':{key:len(result[key])-before[key] for key in before}}
        if selected: result['message'] += ' Targeted crop checks: ' + ', '.join(f"{result['anatomy_refinement']['added'][key]} additional {key}" for key in before) + '.'
        return result
    except (OSError, ValueError, RuntimeError, UnidentifiedImageError):
        return original
    finally:
        source.seek(0)
