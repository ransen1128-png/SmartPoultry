"""Make coordinate reference views for visual annotation; originals stay read-only."""
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'detection/annotation_views'
out.mkdir(parents=True, exist_ok=True)
with (ROOT / 'reports/dataset_audit/visual_family_manifest.csv').open(encoding='utf-8', newline='') as stream:
    rows = list(csv.DictReader(stream))
index = []
for i, row in enumerate(rows, 1):
    with Image.open(row['image']) as raw:
        image = ImageOps.exif_transpose(raw).convert('RGB')
        size = image.size
        display = image.resize((600, 600))
    draw = ImageDraw.Draw(display)
    for n in range(0, 601, 100):
        draw.line([(n, 0), (n, 599)], fill=(130, 200, 220), width=1)
        draw.line([(0, n), (599, n)], fill=(130, 200, 220), width=1)
        draw.text((n + 2, 2), str(n), fill='red', stroke_width=1, stroke_fill='white')
        draw.text((2, n + 2), str(n), fill='red', stroke_width=1, stroke_fill='white')
    display.save(out / f'{i:03}.jpg', quality=92)
    index.append({'index': i, **row, 'width': size[0], 'height': size[1],
                  'coordinate_system': 'Visual review coordinates on 600x600 oriented reference; converted to original pixels on export.'})
(out / 'index.json').write_text(json.dumps(index, indent=2), encoding='utf-8')
print(f'Prepared {len(index)} visual reference images.')
