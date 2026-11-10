"""Execute pretrained anatomy queries and save reviewable predictions, not labels."""
import json
import sys
from pathlib import Path

import torch
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
from core.chicken_detection import load_detector

torch.set_num_threads(4)
artifact = load_detector()
if artifact is None:
    raise SystemExit('OWL-ViT is unavailable.')
processor, model = artifact
labels = ['a photo of a chicken', 'a chicken leg', 'a chicken spur']
out = ROOT / 'detection/probe'
out.mkdir(exist_ok=True)
results = []
for name in ['19months.jpg', '10months.jpg', '3monthsss.jpg', '14months.jpg', '11months.jpg']:
    image = Image.open(ROOT / 'spurs images' / name).convert('RGB')
    inputs = processor(text=[labels], images=image, return_tensors='pt')
    with torch.inference_mode():
        outputs = model(**inputs)
    predictions = processor.post_process_object_detection(
        outputs, target_sizes=torch.tensor([[image.height, image.width]]), threshold=.10)[0]
    boxes = [{'query': labels[int(label)], 'score': float(score), 'box': box}
             for box, score, label in zip(predictions['boxes'].tolist(), predictions['scores'].tolist(), predictions['labels'].tolist())]
    boxes = sorted(boxes, key=lambda r: r['score'], reverse=True)[:20]
    results.append({'image': name, 'predictions': boxes})
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for row in boxes:
        draw.rectangle(row['box'], outline='red', width=2)
        draw.text(row['box'][:2], f"{row['query']} {row['score']:.2f}", fill='red', stroke_width=1, stroke_fill='white')
    overlay.save(out / name)
(out / 'owlvit_predictions.json').write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
