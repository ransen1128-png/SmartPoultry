"""Experimental anatomy inference from local, evaluated model checkpoints.

Age prediction is separate. No image filename/age is used for localization.
"""
import hashlib
import heapq
import json
import logging
import math
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / 'ml_models/poultry_vision'
MANIFEST = MODEL_DIR / 'manifest.json'
INFERENCE_LOCK = threading.RLock()


def _read_manifest():
    try:
        return json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=2)
def _load_bundle(manifest_text):
    manifest = json.loads(manifest_text)
    try:
        from ultralytics import YOLO
        from ultralytics.utils import torch_utils
        from core.ml_runtime import configure_cpu_runtime
        torch_utils.NUM_THREADS = configure_cpu_runtime()
        models = {}
        for task in ('detect', 'segment'):
            entry = manifest[task]
            path = (MODEL_DIR / entry['filename']).resolve()
            if path.parent != MODEL_DIR.resolve() or not path.is_file():
                return None
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                logger.error('Anatomy checkpoint integrity check failed: %s', task)
                return None
            models[task] = YOLO(str(path))
        if models['detect'].names != {0: 'leg', 1: 'spur'} or models['segment'].names != {0: 'spur'}:
            logger.error('Anatomy checkpoint class labels do not match the annotation schema')
            return None
        return {**models, 'manifest': manifest}
    except (ImportError, OSError, RuntimeError, ValueError, KeyError):
        logger.exception('Anatomy models could not be loaded')
        return None


def load_vision_models():
    manifest = _read_manifest()
    return _load_bundle(json.dumps(manifest, sort_keys=True)) if manifest else None


def vision_is_ready():
    return load_vision_models() is not None


def _box_iou(first, second):
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0., x2-x1) * max(0., y2-y1)
    total = ((first[2]-first[0])*(first[3]-first[1])
             + (second[2]-second[0])*(second[3]-second[1]) - intersection)
    return intersection / total if total > 0 else 0.


def _centerline_measurement(polygon, width, height, pixels_per_cm=None):
    """Projected visible centerline in image pixels, not an anatomical 3D length."""
    from scipy.ndimage import label
    from skimage.morphology import skeletonize
    points = np.asarray(polygon, dtype=float)
    if len(points) < 3:
        return None
    x1, y1 = np.floor(points.min(axis=0)).astype(int)
    x2, y2 = np.ceil(points.max(axis=0)).astype(int)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width - 1, x2), min(height - 1, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    factor = min(1., 512. / max(x2-x1+3, y2-y1+3))
    canvas = Image.new('1', (max(3, int((x2-x1+3)*factor)), max(3, int((y2-y1+3)*factor))))
    mapped = [((x-x1+1)*factor, (y-y1+1)*factor) for x, y in points]
    ImageDraw.Draw(canvas).polygon(mapped, fill=1)
    # Pillow mode "1" may expose true bytes as 255. Normalize to canonical
    # writable 0/1 booleans before the native skeletonization lookup table.
    binary = np.array(canvas.convert('L'), dtype=np.uint8, copy=True) > 0
    skeleton = skeletonize(binary)
    components, count = label(skeleton, structure=np.ones((3, 3)))
    if not count:
        return None
    sizes = np.bincount(components.flatten())
    sizes[0] = 0
    skeleton = components == sizes.argmax()
    nodes = {tuple(item) for item in np.argwhere(skeleton)}
    if len(nodes) < 2:
        return None

    def neighbors(node):
        y, x = node
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                other = (y+dy, x+dx)
                if (dy or dx) and other in nodes:
                    yield other, math.sqrt(2) if dx and dy else 1.

    def distances(start):
        distance, previous = {start: 0.}, {}
        queue = [(0., start)]
        while queue:
            value, node = heapq.heappop(queue)
            if value > distance[node]:
                continue
            for other, step in neighbors(node):
                proposed = value + step
                if proposed < distance.get(other, float('inf')):
                    distance[other] = proposed
                    previous[other] = node
                    heapq.heappush(queue, (proposed, other))
        finish = max(distance, key=distance.get)
        return finish, distance[finish], previous

    start = next(iter(nodes))
    start, _, _ = distances(start)
    finish, length, previous = distances(start)
    path = [finish]
    while path[-1] != start:
        path.append(previous[path[-1]])
    # Keep display payload bounded; length uses the full skeleton path.
    stride = max(1, len(path) // 160)
    sampled = path[::stride]
    if sampled[-1] != path[-1]:
        sampled.append(path[-1])
    centerline = [[round(x/factor+x1-1, 1), round(y/factor+y1-1, 1)] for y, x in sampled]
    touches_frame = bool((points[:, 0] <= 1).any() or (points[:, 1] <= 1).any()
                         or (points[:, 0] >= width-2).any() or (points[:, 1] >= height-2).any())
    pixel_length = length / factor
    output = {'status': 'visible_projected_length', 'length_px': round(pixel_length, 2),
              'centerline': centerline, 'truncated_at_frame': touches_frame,
              'method': 'Longest geodesic path on predicted visible-mask skeleton',
              'physical_length_cm': None,
              'limitation': 'Projected visible mask length; not guaranteed anatomical base-to-tip or 3D length.'}
    if pixels_per_cm is not None and not touches_frame:
        calibrated = pixel_length / pixels_per_cm
        if not math.isfinite(calibrated):
            return output
        output['physical_length_cm'] = round(calibrated, 3)
        output['calibration'] = {'pixels_per_cm': pixels_per_cm, 'source': 'user_supplied',
                                 'limitation': 'Valid only for a known in-plane scale and suitable perspective.'}
    return output


def analyze_poultry(source, pixels_per_cm=None):
    result = {'status': 'unavailable', 'legs': [], 'spurs': [], 'masks': [], 'unconfirmed_masks': [],
              'measurements': [], 'image_width': None, 'image_height': None,
              'message': 'Anatomy models are unavailable.'}
    bundle = load_vision_models()
    if bundle is None:
        return result
    try:
        if pixels_per_cm is not None:
            pixels_per_cm = float(pixels_per_cm)
            if not math.isfinite(pixels_per_cm) or pixels_per_cm <= 0:
                raise ValueError('Calibration must be a finite positive pixels-per-centimeter value.')
        source.seek(0)
        with Image.open(source) as raw:
            image = ImageOps.exif_transpose(raw).convert('RGB')
        width, height = image.size
        manifest = bundle['manifest']
        threshold = manifest.get('confidence_threshold', .30)
        with INFERENCE_LOCK:
            detected = bundle['detect'].predict(image, imgsz=512, conf=manifest['detect'].get('threshold', threshold), iou=.45,
                                                 max_det=12, device='cpu', verbose=False)[0]
            segmented = bundle['segment'].predict(image, imgsz=512, conf=manifest['segment'].get('threshold', threshold), iou=.45,
                                                   max_det=6, retina_masks=True, device='cpu', verbose=False)[0]
        result.update(status='completed', image_width=width, image_height=height,
                      model_version=manifest.get('version'), model_provenance={
                          key: {'sha256': manifest[key]['sha256'], 'metrics': manifest[key].get('metrics')}
                          for key in ('detect', 'segment')})
        if detected.boxes is not None:
            for xyxy, score, cls in zip(detected.boxes.xyxy.tolist(), detected.boxes.conf.tolist(), detected.boxes.cls.tolist()):
                key = 'legs' if int(cls) == 0 else 'spurs'
                box = [max(0., min(width, xyxy[0])), max(0., min(height, xyxy[1])),
                       max(0., min(width, xyxy[2])), max(0., min(height, xyxy[3]))]
                result[key].append({'xyxy': [round(v, 1) for v in box], 'score': round(score, 4),
                                    'source': 'experimental_detector'})
        if segmented.masks is not None:
            for polygon, score in zip(segmented.masks.xy, segmented.boxes.conf.tolist()):
                polygon = np.asarray(polygon)
                if len(polygon) < 3:
                    continue
                if len(polygon) > 240:
                    polygon = polygon[::math.ceil(len(polygon)/240)]
                polygon[:, 0] = np.clip(polygon[:, 0], 0, width-1)
                polygon[:, 1] = np.clip(polygon[:, 1], 0, height-1)
                points = [[round(float(x), 1), round(float(y), 1)] for x, y in polygon]
                mask = {'polygon': points, 'score': round(score, 4),
                        'xyxy': [round(float(v), 1) for v in [*polygon.min(axis=0), *polygon.max(axis=0)]]}
                overlaps = [_box_iou(mask['xyxy'], box['xyxy']) for box in result['spurs']]
                if not overlaps or max(overlaps) < .15:
                    result['unconfirmed_masks'].append(mask)
                    continue
                mask['matched_detector_box'] = int(np.argmax(overlaps))
                result['masks'].append(mask)
                measurement = _centerline_measurement(points, width, height, pixels_per_cm)
                if measurement:
                    measurement['mask_index'] = len(result['masks'])-1
                    result['measurements'].append(measurement)
        result['message'] = (f"Experimental models found {len(result['legs'])} leg candidate(s), "
                             f"{len(result['spurs'])} spur box(es) and {len(result['masks'])} spur mask(s). "
                             f"{len(result['unconfirmed_masks'])} outline proposal(s) lacked matching spur boxes. "
                             'No detection above threshold does not establish anatomical absence.')
    except (ImportError, OSError, ValueError, RuntimeError, KeyError):
        logger.exception('Anatomy inference failed')
        result.update(status='error', message='Anatomy inference failed for this image.')
    finally:
        source.seek(0)
    return result


def constrain_legs_to_body(detection, anatomy):
    """Retain raw proposals, suppress leg centers outside all proposed bodies."""
    if detection.get('status') not in ('detected', 'candidate') or not detection.get('boxes') or anatomy.get('status') != 'completed':
        return anatomy
    result = dict(anatomy)
    retained, excluded = [], []
    for leg in anatomy.get('legs', []):
        x1, y1, x2, y2 = leg['xyxy']
        cx, cy = (x1+x2)/2, (y1+y2)/2
        inside = False
        for body in detection['boxes']:
            bx1, by1, bx2, by2 = body['xyxy']
            dx, dy = (bx2-bx1)*.05, (by2-by1)*.05
            inside |= bx1-dx <= cx <= bx2+dx and by1-dy <= cy <= by2+dy
        (retained if inside else excluded).append(leg)
    result.update(legs=retained, out_of_body_leg_candidates=excluded)
    if excluded:
        result['message'] += f' Suppressed {len(excluded)} leg proposal(s) outside proposed chicken bodies; raw proposals retained.'
    return result


def assess_chicken_evidence(detection, anatomy):
    """Combine actual model evidence without claiming species verification."""
    if detection.get('status') == 'detected' and detection.get('boxes'):
        return {'status': 'body_candidate', 'label': 'Yes',
                'explanation': 'The chicken detector found a body candidate. This is a model prediction.'}
    if detection.get('status') == 'candidate' and detection.get('boxes'):
        return {'status': 'body_candidate', 'label': 'Chicken detected',
                'explanation': 'A chicken-related body query found a lower-score candidate.'}
    if anatomy.get('status') == 'completed':
        regions = []
        if anatomy.get('legs'):
            regions.append('leg')
        if anatomy.get('spurs') or anatomy.get('masks'):
            regions.append('spur')
        if regions:
            names = '/'.join(regions)
            return {'status': 'anatomy_candidate',
                    'label': f'{names.capitalize()} regions detected',
                    'explanation': (
                        f'The anatomy models detected {names} regions. Whole-chicken body not detected. '
                        'Age estimation can use a leg or spur photo; anatomy detections alone do not independently verify the species.')}
    return {'status': 'unconfirmed', 'label': 'Chicken not detected',
            'explanation': 'The models did not establish chicken presence. A readable close-up can still receive an experimental age estimate.'}


def summarize_anatomy(result):
    """User-facing status uses actual outputs, with absence distinct from failure."""
    if result['status'] != 'completed':
        message = result.get('message', 'Anatomy inference unavailable.')
        return {'leg_detection_status': message, 'leg_location_assessment': 'Not localized.',
                'spur_detection_status': message, 'spur_location_assessment': 'Not localized.',
                'spur_segmentation_status': 'No segmentation result.', 'spur_visibility': 'Not assessed',
                'spur_length_assessment': 'Not measured; no usable spur mask.', 'spur_visibility_value': 'unassessed'}

    def locations(boxes):
        return '; '.join(f"Box {box['xyxy']} pixels; model score {box['score']:.3f}" for box in boxes) if boxes else 'No region located.'
    spurs = result['spurs'] or result['masks']
    measurements = result['measurements']
    length = '; '.join(f"Spur {m.get('mask_index', i)+1}: {m['length_px']:.1f} pixels of visible spur centerline"
                       + (f"; {m['physical_length_cm']:.2f} cm using your supplied scale" if m['physical_length_cm'] is not None else '')
                       + (' (frame-truncated)' if m['truncated_at_frame'] else '')
                       for i, m in enumerate(measurements))
    if length and not any(m['physical_length_cm'] is not None for m in measurements):
        length += '. Add a known image scale to convert pixels to centimeters.'
    partial = any(m['truncated_at_frame'] for m in measurements)
    return {
        'leg_detection_status': f"Leg detected — {len(result['legs'])} region(s)." if result['legs'] else 'Leg not detected. Upload a closer view of the leg.',
        'leg_location_assessment': locations(result['legs']),
        'spur_detection_status': f"Spur detected — {len(spurs)} region(s)." if spurs else 'Spur not detected. Upload a closer view of the leg and spur.',
        'spur_location_assessment': locations(spurs),
        'spur_segmentation_status': (
            f"Spur outline detected — {len(result['masks'])} outline(s)."
            if result['masks'] else
            ('Outline could not be matched to a detected spur. Upload a closer photo for measurement.'
             if result.get('unconfirmed_masks') else 'Spur outline not detected. A closer photo is needed for measurement.')
        ),
        'spur_visibility': ('Detected region reaches the image edge.' if partial else 'Spur region detected in the photo.') if spurs else 'No spur region detected.',
        'spur_visibility_value': ('partial' if partial else 'clear') if spurs else 'unassessed',
        'spur_length_assessment': length or 'Not measured — a detected spur outline is required.',
    }
