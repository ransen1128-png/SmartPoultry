"""Produce an unfilled review queue from the completed audit, not new labels."""
import csv
import json
from collections import defaultdict
from pathlib import Path

from audit_spur_dataset import write_csv

ROOT = Path(__file__).resolve().parents[1]
audit = ROOT / 'reports/dataset_audit'
summary = json.loads((audit / 'summary.json').read_text())
rows = list(csv.DictReader((audit / 'image_inventory.csv').open(encoding='utf-8', newline='')))
groups = defaultdict(list)
for row in rows:
    if row.get('metadata_rows') == '1' and not row['error']:
        groups[row['pixel_sha256']].append(row)
queue = []
for pixel_hash, members in groups.items():
    representative = members[0]
    queue.append({
        'image': representative['path'], 'sha256': representative['sha256'],
        'pixel_sha256': pixel_hash, 'duplicate_file_count': len(members),
        'age_months': representative['age_months'],
        'recorded_chicken_id': representative['chicken_id'],
        'chicken_id': '', 'identity_verified': '', 'age_verified': 'yes',
        'record_reference': 'User explicitly confirmed existing ages on 2026-11-09',
        'source_family': '', 'content_type': '',
        'spur_visibility': '', 'review_notes': '',
    })
destination = audit / 'review_queue.csv'
if destination.exists():
    raise SystemExit('Review queue already exists; refusing to overwrite human work.')
write_csv(destination, queue)
print(f'Created {len(queue)} review rows; identity/annotation fields are blank and existing ages retain user confirmation.')
