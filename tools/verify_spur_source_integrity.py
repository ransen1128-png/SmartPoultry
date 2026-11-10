"""Verify original image/metadata/checkpoint hashes after training and tests."""
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from audit_spur_dataset import digest

ROOT = Path(__file__).resolve().parents[1]
audit = ROOT / 'reports/dataset_audit'
summary = json.loads((audit / 'summary.json').read_text())
with (audit / 'image_inventory.csv').open(encoding='utf-8', newline='') as stream:
    rows = list(csv.DictReader(stream))


def verify(row):
    path = Path(row['path'])
    if not path.is_file():
        return {'path': str(path), 'issue': 'missing_since_audit'}
    if digest(path) != row['sha256']:
        return {'path': str(path), 'issue': 'changed_since_audit'}
    return None


with ThreadPoolExecutor(max_workers=4) as pool:
    changes = [item for item in pool.map(verify, rows) if item]
metadata_changes = []
for row in summary['metadata_sources']:
    path = ROOT / row['path']
    if not path.is_file() or digest(path) != row['sha256']:
        metadata_changes.append(str(path))
expected_model = 'caf542a63c69a003f85ddeddb6777480e61601f13f3f2d58a82ef0c9cd6ef2b7'
result = {
    'original_workspace_images_checked': len(rows),
    'image_changes': changes, 'metadata_sources_checked': len(summary['metadata_sources']),
    'metadata_changes': metadata_changes,
    'original_checkpoint_unchanged': digest(ROOT / 'spur_age/models/spur_age_model.pth') == expected_model,
    'backup_checkpoint_matches': digest(ROOT / f'spur_age/models/backups/resnet18_{expected_model}.pth') == expected_model,
}
(audit / 'source_integrity.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
if changes or metadata_changes or not result['original_checkpoint_unchanged'] or not result['backup_checkpoint_matches']:
    raise SystemExit(1)
