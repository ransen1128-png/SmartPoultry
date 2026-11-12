"""Text-conditioned chicken detection, independent of the age checkpoint.

Only local weights are loaded: web requests never download a model.
"""
import logging
import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)
DEFAULT_MODEL = Path(__file__).resolve().parents[2] / 'ml_models' / 'chicken_owlvit'
BODY_QUERIES = ['a photo of a chicken', 'a young chicken', 'a hen', 'a rooster']


@lru_cache(maxsize=1)
def load_detector():
    path = Path(os.environ.get('CHICKEN_DETECTOR_PATH', DEFAULT_MODEL))
    if not path.is_dir():
        return None
    try:
        from core.ml_runtime import configure_cpu_runtime
        configure_cpu_runtime()
        from transformers import OwlViTProcessor, OwlViTForObjectDetection
        processor = OwlViTProcessor.from_pretrained(path, local_files_only=True)
        model = OwlViTForObjectDetection.from_pretrained(path, local_files_only=True)
        model.eval()
        return processor, model
    except (ImportError, OSError, RuntimeError, ValueError):
        logger.exception('Chicken detector could not be loaded')
        return None


def detect_chicken(source):
    result = {'status': 'unavailable', 'boxes': [], 'message':
              'Not located; no chicken detector is configured.'}
    artifact = load_detector()
    if artifact is None:
        return result
    try:
        import torch
        source.seek(0)
        with Image.open(source) as raw:
            image = ImageOps.exif_transpose(raw).convert('RGB')
        processor, model = artifact
        inputs = processor(text=[BODY_QUERIES], images=image,
                           return_tensors='pt')
        with torch.inference_mode():
            outputs = model(**inputs)
        detected = processor.post_process_object_detection(
            outputs, target_sizes=torch.tensor([[image.height, image.width]]),
            threshold=0.25,
        )[0]
        boxes = []
        labels = detected.get('labels', torch.zeros(len(detected['scores']), dtype=torch.long)).tolist()
        for box, score, label in zip(detected['boxes'].tolist(), detected['scores'].tolist(), labels):
            x1, y1, x2, y2 = box
            box = [max(0, min(image.width, x1)), max(0, min(image.height, y1)),
                   max(0, min(image.width, x2)), max(0, min(image.height, y2))]
            if box[2] > box[0] and box[3] > box[1]:
                boxes.append({'xyxy': [round(v, 1) for v in box], 'score': round(score, 4),
                              'query': BODY_QUERIES[int(label)]})
        if boxes:
            from torchvision.ops import nms
            keep = nms(torch.tensor([b['xyxy'] for b in boxes]),
                       torch.tensor([b['score'] for b in boxes]), .35).tolist()[:4]
            boxes = [boxes[i] for i in keep]
        status = 'detected' if any(b['score'] >= .35 for b in boxes) else 'candidate' if boxes else 'not_detected'
        result.update(status=status, boxes=boxes,
                      image_width=image.width, image_height=image.height,
                      queries=BODY_QUERIES, candidate_threshold=.25, detection_threshold=.35,
                      message=(('Chicken-body model prediction; lower-score experimental result. ' if status == 'candidate' else '')
                               + '; '.join(f"Box {b['xyxy']} pixels; detector score {b['score']:.3f}; query: {b['query']}"
                                            for b in boxes) if boxes else
                               'No chicken body candidate above the 0.25 threshold. This does not prove absence.'))
    except (OSError, ValueError, RuntimeError):
        logger.exception('Chicken detection failed')
        result.update(status='error', message='Chicken detection failed for this image.')
    finally:
        source.seek(0)
    return result
