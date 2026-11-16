"""Combine local anatomy predictions with API localization for missing regions.

API boxes never become segmentation masks, lengths, confidence scores or labels
for training. The age model and its input remain unchanged.
"""
import copy
import math

from PIL import Image, ImageOps, UnidentifiedImageError

from .vision_api import locate_spurs_with_fallback as locate_spurs, spur_model


def _valid_box(box, width, height):
    return (isinstance(box, (list, tuple)) and len(box) == 4
            and all(type(v) in (int, float) and math.isfinite(v) for v in box)
            and 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height)


def _nearest_leg(box, legs):
    """Associate a region to one nearby leg, without assigning chicken identity."""
    cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
    candidates = []
    for index, leg in enumerate(legs):
        x1, y1, x2, y2 = leg['xyxy']
        side = max(x2-x1, y2-y1)
        if side <= 0:
            continue
        padding = .75 * side
        if x1-padding <= cx <= x2+padding and y1-padding <= cy <= y2+padding:
            distance = ((cx-(x1+x2)/2)**2 + (cy-(y1+y2)/2)**2) / side**2
            candidates.append((distance, index))
    return min(candidates)[1] if candidates else None


def _same_region(first, second):
    """Suppress overlapping or nested boxes; scores from different models aren't averaged."""
    from .poultry_vision import _box_iou
    intersection = (max(0, min(first[2], second[2])-max(first[0], second[0]))
                    * max(0, min(first[3], second[3])-max(first[1], second[1])))
    smaller = min((first[2]-first[0])*(first[3]-first[1]),
                  (second[2]-second[0])*(second[3]-second[1]))
    return _box_iou(first, second) >= .3 or (smaller > 0 and intersection/smaller >= .7)


def _recover_local_outlines(result, added_boxes, pixels_per_cm):
    """Measure only real local segmentation polygons supported by API localization."""
    from .poultry_vision import _box_iou, _centerline_measurement
    unmatched = []
    for original in result.get('unconfirmed_masks', []):
        matches = [( _box_iou(original['xyxy'], result['spurs'][index]['xyxy']), index)
                   for index in added_boxes]
        overlap, box_index = max(matches, default=(0, None))
        if overlap < .15:
            unmatched.append(original)
            continue
        mask = copy.deepcopy(original)
        mask.update(source='local_segmenter_api_localization', matched_api_box=box_index)
        result['masks'].append(mask)
        measured = _centerline_measurement(mask['polygon'], result['image_width'],
                                          result['image_height'], pixels_per_cm)
        if measured:
            measured.update(mask_index=len(result['masks'])-1,
                            source='local_segmenter_api_localization')
            result['measurements'].append(measured)
    result['unconfirmed_masks'] = unmatched


def assist_missed_spurs(source, anatomy, pixels_per_cm=None):
    if anatomy.get('status') != 'completed' or not anatomy.get('legs'):
        return anatomy
    regions = anatomy.get('spurs', []) + anatomy.get('masks', [])
    # Unknown historical geometry cannot safely determine coverage.
    if any(not isinstance(region.get('xyxy'), (list, tuple)) or len(region['xyxy']) != 4
           for region in regions):
        return anatomy
    covered = {_nearest_leg(region['xyxy'], anatomy['legs']) for region in regions}
    missing = set(range(len(anatomy['legs']))) - covered
    if not missing:
        return anatomy

    result = copy.deepcopy(anatomy)
    try:
        source.seek(0)
        with Image.open(source) as raw:
            from .free_inference import check_image_size
            check_image_size(raw)
            image = ImageOps.exif_transpose(raw).convert('RGB')
        model = spur_model()
        api = locate_spurs(image, model=model, timeout=20, max_attempts=2)
        api.setdefault('model', model)
        result['api_spur_assistance'] = copy.deepcopy(api)
        accepted = []
        agreements = 0
        if api.get('status') == 'completed':
            for box in api.get('boxes', []):
                if not _valid_box(box, image.width, image.height):
                    continue
                if any(_same_region(box, region['xyxy']) for region in regions):
                    agreements += 1
                    continue
                leg_index = _nearest_leg(box, result['legs'])
                if leg_index not in missing or any(_same_region(box, region['xyxy']) for region in accepted):
                    continue
                accepted.append({'xyxy': [round(v, 1) for v in box], 'score': None,
                                 'source': 'gemini_api', 'leg_index': leg_index,
                                 'model': api.get('model_version') or api.get('model')})
            first_added = len(result['spurs'])
            result['spurs'].extend(accepted)
            result['api_spur_assistance']['accepted_regions'] = len(accepted)
            result['api_spur_assistance']['local_agreements'] = agreements
            result['api_spur_assistance']['missing_leg_regions'] = sorted(missing)
            result['api_spur_assistance']['region_policy'] = 'Center near a detected leg; this spatial filter is not independent anatomical validation.'
            if accepted and result.get('unconfirmed_masks'):
                _recover_local_outlines(result, range(first_added, len(result['spurs'])), pixels_per_cm)
            result['message'] += (f' Combined analysis retained local predictions and added {len(accepted)} API spur region(s). '
                                  'Lengths use local segmentation polygons only; API boxes alone do not provide a measurement.')
        else:
            result['message'] += ' API spur assistance was unavailable; local predictions and age estimation were retained.'
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        result['api_spur_assistance'] = {'status': 'error', 'boxes': [], 'message': 'This image could not be prepared for API assistance.'}
    finally:
        source.seek(0)
    return result
