"""Run actual local checkpoints on held-out originals; preserve results and overlays."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))

import torch
from PIL import Image, ImageDraw, ImageOps
from core.poultry_vision import analyze_poultry
from core.rooster_age_classifier import predict_rooster_age


def main():
    torch.set_num_threads(4)
    output = ROOT / 'detection/smoke'
    output.mkdir(exist_ok=True)
    rows = json.loads((ROOT / 'detection/annotation_manifest.json').read_text())
    samples = [row for row in rows if row['split'] == 'test']
    results = []
    for row in samples:
        path = Path(row['image'])
        with path.open('rb') as source:
            result = analyze_poultry(source)
            source.seek(0)
            age = predict_rooster_age(source)
        if result['status'] != 'completed' or age is None:
            raise RuntimeError(f'Inference failed: {path}')
        with Image.open(path) as raw:
            image = ImageOps.exif_transpose(raw).convert('RGB')
        draw = ImageDraw.Draw(image)
        for name, color in [('legs', 'yellow'), ('spurs', 'magenta')]:
            for box in result[name]:
                draw.rectangle(box['xyxy'], outline=color, width=3)
        for mask in result['masks']:
            points = [tuple(p) for p in mask['polygon']]
            draw.line(points + [points[0]], fill='cyan', width=3)
        image.thumbnail((420, 420))
        image.save(output / f"test_{row['index']}.jpg")
        results.append({'index': row['index'], 'split': 'test', 'source_family': row['source_family'],
                        'age': age, 'anatomy': result})
    (output / 'actual_inference.json').write_text(json.dumps(results, indent=2))
    sheet = Image.new('RGB', (1680, 900), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, result in enumerate(results):
        with Image.open(output / f"test_{result['index']}.jpg") as image:
            x, y = i % 4 * 420, i // 4 * 450
            sheet.paste(image, (x, y))
            a = result['anatomy']
            draw.text((x+5, y+425), f"{result['index']}: legs {len(a['legs'])}, spurs {len(a['spurs'])}, masks {len(a['masks'])}", fill='black')
    sheet.save(output / 'heldout_overlays.jpg')
    print(json.dumps([{'index': r['index'], 'age': r['age']['age_months'],
                        'legs': len(r['anatomy']['legs']), 'spurs': len(r['anatomy']['spurs']),
                        'masks': len(r['anatomy']['masks'])} for r in results], indent=2))


if __name__ == '__main__':
    main()
