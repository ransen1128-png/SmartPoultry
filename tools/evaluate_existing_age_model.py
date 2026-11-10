"""Evaluate the preserved checkpoint; explicitly NOT an independent test.

Requires the completed read-only audit. Identical files share an inference only,
not a fabricated label. Every existing labeled image receives an output row.
"""
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.model_selection import GroupShuffleSplit
from torchvision import models, transforms

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from audit_spur_dataset import write_csv


def metrics(rows):
    if not rows:
        return {'n': 0, **{key: None for key in (
            'mae_months', 'median_absolute_error_months', 'rmse_months', 'bias_months',
            'within_1_month_fraction', 'within_3_months_fraction', 'p90_absolute_error_months')}}
    errors = np.array([float(r['prediction_months']) - float(r['age_months']) for r in rows])
    return {'n': len(rows), 'mae_months': float(np.abs(errors).mean()),
            'median_absolute_error_months': float(np.median(np.abs(errors))),
            'rmse_months': float(np.sqrt((errors ** 2).mean())),
            'bias_months': float(errors.mean()),
            'within_1_month_fraction': float((np.abs(errors) <= 1).mean()),
            'within_3_months_fraction': float((np.abs(errors) <= 3).mean()),
            'p90_absolute_error_months': float(np.quantile(np.abs(errors), .9))}


def main():
    torch.set_num_threads(4)
    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True)
    audit = ROOT / 'reports' / 'dataset_audit'
    out = ROOT / 'reports' / 'existing_model_evaluation'
    out.mkdir(parents=True, exist_ok=True)
    inventory = list(csv.DictReader((audit / 'image_inventory.csv').open(encoding='utf-8', newline='')))
    images = [r for r in inventory if r.get('metadata_rows') == '1' and not r['error']]
    unique = {r['sha256']: r for r in images}
    model_path = ROOT / 'spur_age' / 'models' / 'spur_age_model.pth'
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=True)
    model = models.resnet18(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, 1)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    transform = transforms.Compose([
        transforms.Resize((checkpoint['image_size'], checkpoint['image_size'])),
        transforms.ToTensor(),
        transforms.Normalize(checkpoint['normalization_mean'], checkpoint['normalization_std']),
    ])
    predictions = {}
    representatives = list(unique.values())
    with torch.inference_mode():
        for start in range(0, len(representatives), 16):
            batch = representatives[start:start + 16]
            tensors = []
            for row in batch:
                with Image.open(row['path']) as image:
                    tensors.append(transform(image.convert('RGB')))
            raw = model(torch.stack(tensors)).flatten().tolist()
            for row, value in zip(batch, raw):
                predictions[row['sha256']] = (value, max(1., min(24., value)))
            print(f'Evaluated {min(start + 16, len(representatives))}/{len(representatives)} distinct files', flush=True)
    metadata = list(csv.DictReader((ROOT / 'spur_age/dataset/metadata.csv').open(encoding='utf-8-sig', newline='')))
    splitter = GroupShuffleSplit(n_splits=1, test_size=.2, random_state=42)
    train_idx, test_idx = next(splitter.split(metadata, groups=[r['chicken_id'] for r in metadata]))
    train_names = {metadata[i]['image'].casefold() for i in train_idx}
    test_names = {metadata[i]['image'].casefold() for i in test_idx}
    train_pixels = {r['pixel_sha256'] for r in images if Path(r['path']).name.casefold() in train_names}
    results = []
    for row in images:
        value, clipped = predictions[row['sha256']]
        results.append({
            'image': Path(row['path']).name, 'sha256': row['sha256'],
            'chicken_id_as_recorded': row['chicken_id'], 'age_months': float(row['age_months']),
            'raw_prediction_months': value, 'prediction_months': clipped,
            'error_months': clipped - float(row['age_months']),
            'absolute_error_months': abs(clipped - float(row['age_months'])),
            'reconstructed_split': 'test' if Path(row['path']).name.casefold() in test_names else 'train',
            'identical_pixels_in_reconstructed_train': row['pixel_sha256'] in train_pixels,
        })
    test = [r for r in results if r['reconstructed_split'] == 'test']
    distinct_results = list({r['sha256']: r for r in results}.values())
    by_age = [{'age_months': age, **metrics([r for r in results if r['age_months'] == age]),
               'distinct_file_mae_months': metrics([r for r in distinct_results if r['age_months'] == age])['mae_months']}
              for age in range(1, 25)]
    grouped = [{'age_group': f'{lo}-{lo + 5}', **metrics([r for r in results if lo <= r['age_months'] <= lo + 5])}
               for lo in (1, 7, 13, 19)]
    confusion = np.zeros((24, 24), dtype=int)
    for row in results:
        confusion[int(row['age_months']) - 1, int(np.floor(row['prediction_months'] + .5)) - 1] += 1
    write_csv(out / 'predictions.csv', results)
    write_csv(out / 'per_age.csv', by_age)
    write_csv(out / 'per_age_group.csv', grouped)
    write_csv(out / 'confusion_rounded_months.csv', (
        {'actual_age': age + 1, **{f'predicted_{p + 1}': int(confusion[age, p]) for p in range(24)}} for age in range(24)))
    training_median = float(np.median([float(metadata[i]['age_months']) for i in train_idx]))
    baseline = [{**r, 'prediction_months': training_median} for r in test]
    summary = {
        'checkpoint_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
        'checkpoint_metadata': {k: v for k, v in checkpoint.items() if k != 'model_state_dict'},
        'status': 'diagnostic_only_not_independent_validation',
        'limitations': [
            'Checkpoint contains no original split manifest; reconstructed split uses current metadata and original script seed/algorithm.',
            'Image IDs do not establish chicken identity. Exact duplicate leakage is measured below.',
            'Full-corpus and distinct-file evaluations include data potentially used for original training.',
            'Metadata age_verified flags do not independently establish age provenance.',
            'No new model was trained; no independent validation or independent test result is claimed.',
        ],
        'full_corpus': metrics(results), 'distinct_files': metrics(distinct_results),
        'reconstructed_test': metrics(test),
        'reconstructed_train_rows': len(train_idx), 'reconstructed_test_rows': len(test_idx),
        'available_reconstructed_test_images': len(test),
        'test_images_identical_to_train': sum(r['identical_pixels_in_reconstructed_train'] for r in test),
        'test_leakage_fraction': sum(r['identical_pixels_in_reconstructed_train'] for r in test) / len(test),
        'constant_training_median_months': training_median,
        'constant_median_reconstructed_test': metrics(baseline),
        'per_age_group': grouped, 'per_age': by_age,
        'torch_version': str(torch.__version__), 'device': 'cpu',
        'independent_validation': None, 'independent_test': None, 'new_model_comparison': None,
    }
    (out / 'metrics.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k not in {'per_age', 'checkpoint_metadata'}}, indent=2))


if __name__ == '__main__':
    main()
