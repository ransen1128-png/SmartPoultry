"""Export visually reviewed annotations to separate derived training datasets."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from sklearn.model_selection import GroupShuffleSplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    root = ROOT / 'detection'
    original = json.loads((root / 'annotation_views/index.json').read_text())
    annotation_path = root / 'manual_annotations.json'
    document = json.loads(annotation_path.read_text())
    manual = document['images']
    rows, excluded = [], []
    for item in original:
        annotations = manual.get(str(item['index']))
        if annotations is None:
            excluded.append({**item, 'reason': 'Whole-bird/frame family reviewed in contact sheets; small spur boundaries unresolved. Not a negative label.'})
            continue
        if not annotations['complete']:
            excluded.append({**item, 'reason': annotations.get('note', 'Annotation completeness uncertain'),
                             'reviewed_annotations': annotations})
            continue
        if hashlib.sha256(Path(item['image']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f"Original image changed: {item['image']}")
        for box in annotations['legs']:
            x1, y1, x2, y2 = box
            if not (0 <= x1 < x2 <= 600 and 0 <= y1 < y2 <= 600):
                raise ValueError(f"Invalid reviewed box for image {item['index']}")
        for polygon in annotations['spurs']:
            points = np.array(polygon, dtype=float)
            area = abs(np.dot(points[:, 0], np.roll(points[:, 1], 1)) - np.dot(points[:, 1], np.roll(points[:, 0], 1))) / 2
            if len(points) < 3 or area < 3 or points.min() < 0 or points.max() > 600:
                raise ValueError(f"Invalid reviewed polygon for image {item['index']}")
        rows.append({**item, 'annotations': annotations})
    groups = np.array([r['source_family'] for r in rows])
    train_val, test = next(GroupShuffleSplit(n_splits=1, test_size=.20, random_state=2026).split(rows, groups=groups))
    train_rel, val_rel = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=2027).split(train_val, groups=groups[train_val]))
    partitions = {'train': train_val[train_rel].tolist(), 'val': train_val[val_rel].tolist(), 'test': test.tolist()}
    family_split = {}
    manifest = []
    for split, indices in partitions.items():
        for index in indices:
            row = rows[index]
            family = row['source_family']
            if family in family_split and family_split[family] != split:
                raise ValueError('Source-family split leakage')
            family_split[family] = split
            manifest.append({**row, 'split': split})
            filename = row['pixel_sha256'][:24]
            with Image.open(row['image']) as raw:
                image = ImageOps.exif_transpose(raw).convert('RGB')
            for task in ('detect', 'segment'):
                dataset = root / 'derived' / task
                images = dataset / 'images' / split
                labels = dataset / 'labels' / split
                images.mkdir(parents=True, exist_ok=True)
                labels.mkdir(parents=True, exist_ok=True)
                image.save(images / f'{filename}.jpg', quality=96)
                lines = []
                if task == 'detect':
                    for box in row['annotations']['legs']:
                        x1, y1, x2, y2 = box
                        lines.append(f'0 {(x1+x2)/1200:.8f} {(y1+y2)/1200:.8f} {(x2-x1)/600:.8f} {(y2-y1)/600:.8f}')
                    for polygon in row['annotations']['spurs']:
                        points = np.asarray(polygon)
                        x1, y1 = points.min(axis=0)
                        x2, y2 = points.max(axis=0)
                        lines.append(f'1 {(x1+x2)/1200:.8f} {(y1+y2)/1200:.8f} {(x2-x1)/600:.8f} {(y2-y1)/600:.8f}')
                else:
                    for polygon in row['annotations']['spurs']:
                        lines.append('0 ' + ' '.join(f'{value/600:.8f}' for point in polygon for value in point))
                (labels / f'{filename}.txt').write_text('\n'.join(lines) + '\n')
    for task in ('detect', 'segment'):
        dataset = root / 'derived' / task
        names = 'names:\n  0: leg\n  1: spur\n' if task == 'detect' else 'names:\n  0: spur\n'
        (dataset / 'data.yaml').write_text(f'path: {dataset.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\n{names}')
    review = root / 'annotation_review'
    review.mkdir(exist_ok=True)
    for start in range(0, len(rows), 12):
        sheet = Image.new('RGB', (1200, 960), 'white')
        draw_sheet = ImageDraw.Draw(sheet)
        for j, row in enumerate(rows[start:start+12]):
            with Image.open(row['image']) as raw:
                image = ImageOps.exif_transpose(raw).convert('RGB').resize((600, 600))
            draw = ImageDraw.Draw(image)
            for box in row['annotations']['legs']:
                draw.rectangle(box, outline='yellow', width=3)
            for polygon in row['annotations']['spurs']:
                draw.line([tuple(p) for p in polygon] + [tuple(polygon[0])], fill='cyan', width=4)
            x, y = j % 4 * 300, j // 4 * 320
            sheet.paste(image.resize((300, 300)), (x, y))
            draw_sheet.text((x+3, y+302), f"Image {row['index']} ({row['source_family']})", fill='black')
        sheet.save(review / f'sheet_{start//12+1}.jpg', quality=94)
    (root / 'annotation_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (root / 'excluded_annotation_records.json').write_text(json.dumps(excluded, indent=2), encoding='utf-8')
    summary = {'distinct_originals': len(original), 'detailed_review_records': len(manual),
               'training_eligible_images': len(rows), 'excluded_with_reasons': len(excluded),
               'leg_boxes': sum(len(r['annotations']['legs']) for r in rows),
               'spur_polygons': sum(len(r['annotations']['spurs']) for r in rows),
               'splits': {key: len(value) for key, value in partitions.items()},
               'source_families': len(set(groups)), 'source_family_leakage': False,
               'actual_chicken_identity_verified': False,
               'annotation_sha256': hashlib.sha256(annotation_path.read_bytes()).hexdigest(),
               'provenance': document['reviewer'],
               'caution': 'Assistant visual annotations, not independent expert verification. Coarse and partial contours are flagged. No physical scale or bird identity invented.'}
    (root / 'annotation_summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
