"""Fail closed unless body or spur detections support running the age model."""
import math


def _box(region):
    box = region.get('xyxy', [])
    return (isinstance(box, (list, tuple)) and len(box) == 4 and all(type(v) in (int, float) and math.isfinite(v) for v in box)
            and 0 <= box[0] < box[2] and 0 <= box[1] < box[3])


def verify_subject(detection, anatomy):
    if detection.get('status') == 'detected' and any(
        _box(box) and type(box.get('score')) in (int, float) and math.isfinite(box['score']) and box['score'] >= .35
        for box in detection.get('boxes', [])
    ):
        return {'accepted': True, 'source': 'chicken_detector', 'message': 'Chicken body detected; age estimation is allowed.'}
    for box in anatomy.get('spurs', []) if anatomy.get('status') == 'completed' else []:
        if not _box(box):
            continue
        api = anatomy.get('api_spur_assistance') or {}
        if box.get('source') == 'gemini_api' and api.get('status') == 'completed':
            return {'accepted': True, 'source': 'spur_api', 'message': 'Chicken spur region detected; age estimation is allowed.'}
        if type(box.get('score')) in (int, float) and math.isfinite(box['score']) and box['score'] >= .5:
            return {'accepted': True, 'source': 'spur_detector', 'message': 'Spur detected; age estimation is allowed.'}
    return {'accepted': False, 'source': 'none', 'message':
        'No age estimate: a chicken or chicken spur could not be verified. Upload a clear chicken or spur photo. '
        'If detection is unavailable, try again later.'}
