"""Inspect body-query failures using actual local OWL-ViT predictions."""
import json
import sys
from pathlib import Path
import torch
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
from core.chicken_detection import load_detector

torch.set_num_threads(4)
processor, model = load_detector()
queries = ['a photo of a chicken', 'a chicken', 'a hen', 'a rooster', 'a young chicken']
results = []
for name in ['4months.jpg', '11months.jpg', '19months.jpg', '10months.jpg']:
    with Image.open(ROOT / 'spurs images' / name) as raw:
        image = ImageOps.exif_transpose(raw).convert('RGB')
    inputs = processor(text=[queries], images=image, return_tensors='pt')
    with torch.inference_mode():
        output = model(**inputs)
    result = processor.post_process_object_detection(output, target_sizes=torch.tensor([[image.height, image.width]]), threshold=.05)[0]
    rows = sorted([{'query': queries[int(label)], 'score': score, 'xyxy': box}
                   for box, score, label in zip(result['boxes'].tolist(), result['scores'].tolist(), result['labels'].tolist())],
                  key=lambda row: row['score'], reverse=True)[:12]
    results.append({'image': name, 'predictions': rows})
(ROOT / 'detection/probe/body_queries.json').write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
