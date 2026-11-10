"""Read-only corpus inspection. Writes reports/derived previews, never source data."""
import argparse
import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

EXTENSIONS = {'.jpg', '.jpeg', '.jfif', '.png', '.webp', '.bmp', '.tif', '.tiff', '.gif'}
EXCLUDE = {'.venv', 'venv', '.git', '.cache-huggingface', '__pycache__', 'staticfiles', 'reports'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inspect(path):
    row = {'path': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': '',
           'pixel_sha256': '', 'dhash': '', 'width': '', 'height': '', 'format': '', 'error': ''}
    try:
        row['sha256'] = digest(path)
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()  # verify() alone does not fully decode image data
            rgb = ImageOps.exif_transpose(image).convert('RGB')
            row.update(width=rgb.width, height=rgb.height, format=image.format)
            h = hashlib.sha256(f'{rgb.width},{rgb.height},RGB:'.encode())
            h.update(rgb.tobytes())
            row['pixel_sha256'] = h.hexdigest()
            small = np.asarray(rgb.convert('L').resize((9, 8)))
            bits = (small[:, 1:] > small[:, :-1]).flatten()
            row['dhash'] = f'{sum(int(bit) << i for i, bit in enumerate(bits)):016x}'
    except Exception as exc:
        row['error'] = f'{type(exc).__name__}: {exc}'
    return row


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else ['path'])
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def sheet(paths, destination, labels=None):
    pages = []
    for page in range(math.ceil(len(paths) / 60)):
        subset = paths[page * 60:(page + 1) * 60]
        canvas = Image.new('RGB', (1200, math.ceil(len(subset) / 6) * 150), 'white')
        draw = ImageDraw.Draw(canvas)
        for i, path in enumerate(subset):
            try:
                with Image.open(path) as image:
                    thumb = ImageOps.contain(ImageOps.exif_transpose(image).convert('RGB'), (194, 122))
                x, y = (i % 6) * 200, (i // 6) * 150
                canvas.paste(thumb, (x, y))
                label = labels.get(str(path), path.name) if labels else path.name
                draw.text((x + 2, y + 124), str(label)[:31], fill='black')
            except Exception:
                pass
        target = destination.with_name(f'{destination.stem}_{page + 1}.jpg')
        canvas.save(target, quality=88)
        pages.append(str(target))
    return pages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('reports/dataset_audit'))
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    image_paths, metadata_paths, annotation_paths = [], [], []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE)
        for name in sorted(names):
            path = Path(base) / name
            if path.suffix.lower() in EXTENSIONS:
                image_paths.append(path)
            if path.suffix.lower() in {'.csv', '.xlsx', '.xls', '.parquet', '.json', '.jsonl', '.xml', '.yaml', '.yml', '.txt'}:
                # Inventory all potential annotations; dependency/model config is not ground truth.
                annotation_paths.append({'path': str(path.relative_to(root)), 'bytes': path.stat().st_size})
            if path.suffix.lower() == '.csv':
                metadata_paths.append(path)
    corpus_dir = root / 'spur_age' / 'dataset' / 'images'
    print(f'Inventory: {len(image_paths)} workspace images; fully decoding/hashing each.', flush=True)
    images = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, row in enumerate(pool.map(inspect, image_paths)):
            images.append(row)
            if (i + 1) % 1000 == 0:
                print(f'Inspected {i + 1}/{len(image_paths)}', flush=True)
    by_path = {r['path'].casefold(): r for r in images}
    all_metadata, sources, issues, source_conflicts = [], [], [], []
    for path in metadata_paths:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            fields = reader.fieldnames
        sources.append({'path': str(path.relative_to(root)), 'sha256': digest(path),
                        'rows': len(rows), 'columns': fields,
                        'age_counts': dict(Counter(r.get('age_months', '') for r in rows)),
                        'verification_values': dict(Counter(r.get('age_verified', '') for r in rows)),
                        'unique_nonempty_ids': len({r.get('chicken_id', '').strip() for r in rows} - {''})})
        for index, row in enumerate(rows, 2):
            filename = row.get('image', '').strip()
            candidates = [path.parent / 'images' / filename, path.parent / filename, root / filename,
                          corpus_dir / filename, root / 'spurs images' / filename]
            found = next((p.resolve() for p in candidates if filename and p.is_file()), None)
            age = row.get('age_months', '').strip()
            try:
                age_number = float(age)
                valid = math.isfinite(age_number) and 1 <= age_number <= 24
            except (TypeError, ValueError):
                valid = False
            record = {'source': str(path.relative_to(root)), 'row': index, 'image': filename,
                      'resolved_path': str(found) if found else '', 'age_months': age,
                      'chicken_id': row.get('chicken_id', '').strip(),
                      'age_verified': row.get('age_verified', '').strip(),
                      'valid_age': valid, 'notes': row.get('notes', '')}
            all_metadata.append(record)
            for issue, condition in [('missing_image', not found), ('invalid_age', not valid),
                                     ('missing_chicken_id', not record['chicken_id'])]:
                if condition:
                    issues.append({**record, 'issue': issue})
    primary_name = 'spur_age/dataset/metadata.csv'
    primary = [r for r in all_metadata if r['source'].replace('\\', '/') == primary_name]
    primary_by_path = defaultdict(list)
    for row in primary:
        if row['resolved_path']:
            primary_by_path[row['resolved_path'].casefold()].append(row)
    corpus = [r for r in images if Path(r['path']).parent == corpus_dir]
    for row in corpus:
        labels = primary_by_path.get(row['path'].casefold(), [])
        row['metadata_rows'] = len(labels)
        row['age_months'] = labels[0]['age_months'] if len(labels) == 1 else ''
        row['chicken_id'] = labels[0]['chicken_id'] if len(labels) == 1 else ''
    groups = {}
    for key in ('sha256', 'pixel_sha256', 'dhash'):
        indexed = defaultdict(list)
        for row in images:
            if row[key]:
                indexed[row[key]].append(row)
        groups[key] = indexed
        write_csv(out / f'{key}_duplicate_groups.csv', (
            {'hash': h, 'count': len(items), 'paths_json': json.dumps([r['path'] for r in items]),
             'ages_json': json.dumps(sorted({str(r.get('age_months', '')) for r in items})),
             'chicken_ids_json': json.dumps(sorted({r.get('chicken_id', '') for r in items}))}
            for h, items in indexed.items() if len(items) > 1))
    historical = defaultdict(list)
    for row in all_metadata:
        historical[row['image'].casefold()].append(row)
    for name, rows in historical.items():
        ages = {r['age_months'] for r in rows}
        ids = {r['chicken_id'] for r in rows if r['chicken_id']}
        if len(ages) > 1 or len(ids) > 1:
            source_conflicts.append({'image': name, 'age_values': json.dumps(sorted(ages)),
                                     'id_values': json.dumps(sorted(ids)),
                                     'records_json': json.dumps(rows)})
    corpus_groups = defaultdict(list)
    for row in corpus:
        if row['pixel_sha256']:
            corpus_groups[row['pixel_sha256']].append(row)
    conflicts = []
    for h, rows in corpus_groups.items():
        ages = {r['age_months'] for r in rows if r['age_months']}
        ids = {r['chicken_id'] for r in rows if r['chicken_id']}
        if len(ages) > 1 or len(ids) > 1:
            conflicts.append({'pixel_sha256': h, 'images': len(rows), 'age_labels': json.dumps(sorted(ages)),
                              'chicken_ids': json.dumps(sorted(ids)),
                              'paths_json': json.dumps([r['path'] for r in rows])})
    write_csv(out / 'image_inventory.csv', images, list(dict.fromkeys(list(images[0]) + ['metadata_rows', 'age_months', 'chicken_id'])))
    write_csv(out / 'all_metadata_rows.csv', all_metadata)
    write_csv(out / 'metadata_issues.csv', issues)
    write_csv(out / 'historical_metadata_differences.csv', source_conflicts)
    write_csv(out / 'identical_image_label_id_conflicts.csv', conflicts)
    write_csv(out / 'annotation_file_inventory.csv', annotation_paths)
    age_rows = []
    for age in range(1, 25):
        key = str(age)
        labeled = [r for r in primary if r['age_months'] == key]
        actual = [r for r in corpus if r.get('age_months') == key]
        age_rows.append({'age_months': age, 'metadata_rows': len(labeled), 'present_images': len(actual),
                         'missing_images': sum(not r['resolved_path'] for r in labeled),
                         'decoded_pixel_unique': len({r['pixel_sha256'] for r in actual if not r['error']}),
                         'corrupt_images': sum(bool(r['error']) for r in actual)})
    write_csv(out / 'age_distribution.csv', age_rows)
    selected = []
    for age in range(1, 25):
        seen = set()
        for row in corpus:
            if row.get('age_months') == str(age) and not row['error'] and row['pixel_sha256'] not in seen:
                selected.append(Path(row['path']))
                seen.add(row['pixel_sha256'])
                if len(seen) == 3:
                    break
    sheets = sheet(selected, out / 'age_samples.jpg')
    sources_images = [Path(r['path']) for r in images if Path(r['path']).parent == root / 'spurs images' and not r['error']]
    sheets += sheet(sources_images, out / 'source_samples.jpg')
    summary = {
        'generated_utc': datetime.now(timezone.utc).isoformat(), 'root': str(root),
        'scope': 'Workspace excluding environment/cache/static/reports directories; all original dataset folders included.',
        'workspace_image_files': len(images), 'dataset_image_files': len(corpus),
        'other_source_folder_images': len(sources_images), 'primary_metadata_rows': len(primary),
        'primary_missing_files': sum(not r['resolved_path'] for r in primary),
        'primary_invalid_ages': sum(not r['valid_age'] for r in primary),
        'primary_duplicate_image_references': sum(v - 1 for v in Counter(r['image'].casefold() for r in primary).values()),
        'dataset_images_without_primary_label': sum(not primary_by_path.get(r['path'].casefold()) for r in corpus),
        'corrupt_dataset_images': sum(bool(r['error']) for r in corpus),
        'corrupt_workspace_images': sum(bool(r['error']) for r in images),
        'dataset_unique_file_hashes': len({r['sha256'] for r in corpus if r['sha256']}),
        'dataset_unique_decoded_pixel_hashes': len(corpus_groups),
        'dataset_duplicate_decoded_pixel_excess': sum(len(r) - 1 for r in corpus_groups.values()),
        'identical_pixel_groups_with_multiple_ids': sum(len({r['chicken_id'] for r in rows if r['chicken_id']}) > 1 for rows in corpus_groups.values()),
        'identical_pixel_groups_with_conflicting_ages': sum(len({r['age_months'] for r in rows if r['age_months']}) > 1 for rows in corpus_groups.values()),
        'primary_nonempty_chicken_ids': len({r['chicken_id'] for r in primary if r['chicken_id']}),
        'primary_id_provenance': 'Unverified; unique per-image IDs are not evidence of distinct chickens.',
        'metadata_sources': sources, 'age_distribution': age_rows, 'contact_sheets': sheets,
        'dhash_limit': 'Matching difference hashes are review candidates, not proof of identity or safe automatic deduplication.',
        'visual_coverage': 'All images decoded; only contact-sheet examples visually reviewed. Semantic content of every photograph is not verified.',
    }
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    from inspect_spur_embedded_metadata import export_metadata
    export_metadata(out)
    print(json.dumps({k: v for k, v in summary.items() if k not in {'metadata_sources', 'age_distribution'}}, indent=2), flush=True)


if __name__ == '__main__':
    main()
