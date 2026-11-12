"""Train image-feature age corrections; select on validation, evaluate held-out once.

The original model has prior corpus overlap. These are source-family diagnostics,
not independent-chicken validation. Original photos/labels/checkpoint stay intact.
"""
import csv
import hashlib
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import Ridge
from torchvision import models, transforms

ROOT = Path(__file__).resolve().parents[1]


def score(y, prediction):
    error = np.clip(prediction, 1, 24) - y
    return {'n': len(y), 'mae_months': float(np.abs(error).mean()),
            'bias_months': float(error.mean()), 'within_1_month_fraction': float((np.abs(error) <= 1).mean()),
            'within_3_months_fraction': float((np.abs(error) <= 3).mean())}


def main():
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    source = ROOT / 'spur_age/experiments/20261109T074813049131Z/split_manifest.csv'
    rows = list(csv.DictReader(source.open(encoding='utf-8', newline='')))
    groups = {}
    for row in rows:
        for token in (row['pixel_sha256'], row['source_family']):
            if token in groups and groups[token] != row['split']:
                raise RuntimeError('Derivative family crosses partitions')
            groups[token] = row['split']
        if row['age_verified'] != 'yes' or not 1 <= float(row['age_months']) <= 24:
            raise ValueError('Unverified/invalid original age')
        if hashlib.sha256(Path(row['image']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Source image changed')
    active = ROOT / 'spur_age/models/spur_age_model.pth'
    base_hash = hashlib.sha256(active.read_bytes()).hexdigest()
    checkpoint = torch.load(active, map_location='cpu', weights_only=True)
    model = models.resnet18(weights=None)
    model.fc = torch.nn.Linear(512, 1)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    embedding = torch.nn.Sequential(*list(model.children())[:-1], torch.nn.Flatten()).eval()
    prep = transforms.Compose([transforms.Resize((checkpoint['image_size'], checkpoint['image_size'])),
                               transforms.ToTensor(), transforms.Normalize(checkpoint['normalization_mean'], checkpoint['normalization_std'])])
    bank, baseline = [], []
    with torch.inference_mode():
        for row in rows:
            with Image.open(row['image']) as image:
                tensor = prep(image.convert('RGB')).unsqueeze(0)
            features = embedding(tensor)
            bank.append(features[0].numpy())
            baseline.append(model.fc(features).item())
    x = np.asarray(bank, dtype=np.float64)
    baseline = np.asarray(baseline)
    y = np.asarray([float(row['age_months']) for row in rows])
    split = {name: np.array([i for i, row in enumerate(rows) if row['split'] == name])
             for name in ('train', 'validation', 'test')}
    train, validation = split['train'], split['validation']
    counts = Counter(rows[i]['source_family'] for i in train)
    weights = np.array([1/counts[rows[i]['source_family']] for i in train])
    weights *= len(weights)/weights.sum()
    mean = np.average(x[train], axis=0, weights=weights)
    scale = np.maximum(np.sqrt(np.average((x[train]-mean)**2, axis=0, weights=weights)), .01)
    z = (x-mean)/scale
    run = ROOT / 'spur_age/experiments' / ('age_correction_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    run.mkdir(parents=True)
    candidates = []
    candidates.append({'name': 'original', 'coef': np.zeros(512), 'intercept': 0.})
    # Fit a regularized image-feature residual. Filenames, ordering and IDs
    # never enter the network or regression inputs.
    for alpha in (1., 10., 100., 1000., 10000.):
        regression = Ridge(alpha=alpha, solver='svd').fit(z[train], y[train]-baseline[train], sample_weight=weights)
        candidates.append({'name': f'image_residual_ridge_{alpha:g}',
                           'coef': regression.coef_, 'intercept': float(regression.intercept_)})
    median_residual = float(np.median(y[train]-baseline[train]))
    candidates.append({'name': 'training_median_bias', 'coef': np.zeros(512), 'intercept': median_residual})
    for candidate in candidates:
        prediction = baseline + z @ candidate['coef'] + candidate['intercept']
        candidate['validation'] = score(y[validation], prediction[validation])
    selected = min(candidates, key=lambda item: item['validation']['mae_months'])
    selected_prediction = np.clip(baseline + z @ selected['coef'] + selected['intercept'], 1, 24)
    report = {'selected': selected['name'], 'selected_by': 'Lowest validation MAE only',
              'split_counts': {name: len(indices) for name, indices in split.items()},
              'checkpoint_sha256': base_hash, 'seed': 42, 'source_family_leakage': False,
              'independence': 'Original checkpoint has prior corpus overlap; bird IDs unresolved. Not independent-chicken validation.',
              'validation_candidates': [{'name': item['name'], **item['validation']} for item in candidates]}
    for name, indices in split.items():
        report[name] = {'original': score(y[indices], baseline[indices]),
                        'selected': score(y[indices], selected_prediction[indices])}
    report['per_age'] = {str(age): {'original': score(y[indices], baseline[indices]),
                                  'selected': score(y[indices], selected_prediction[indices])}
                         for age in range(1, 25) if len(indices := np.flatnonzero(y == age))}
    # Release gating is conservative; do not tune again using test outcomes.
    report['eligible_for_experimental_release'] = (
        report['validation']['selected']['mae_months'] < report['validation']['original']['mae_months']-.05
        and report['test']['selected']['mae_months'] < report['test']['original']['mae_months']-.05)
    np.savez(run / 'correction.npz', mean=mean, scale=scale, coef=selected['coef'], intercept=np.array(selected['intercept']))
    with (run / 'predictions.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['image', 'sha256', 'source_family', 'split', 'verified_age_months', 'original_prediction', 'selected_prediction', 'absolute_error'])
        writer.writeheader()
        for i, row in enumerate(rows):
            writer.writerow({'image': row['image'], 'sha256': row['sha256'], 'source_family': row['source_family'],
                             'split': row['split'], 'verified_age_months': y[i], 'original_prediction': float(np.clip(baseline[i], 1, 24)),
                             'selected_prediction': selected_prediction[i], 'absolute_error': abs(y[i]-selected_prediction[i])})
    assert hashlib.sha256(active.read_bytes()).hexdigest() == base_hash
    report['original_checkpoint_unchanged'] = True
    report['run'] = str(run)
    (run / 'report.json').write_text(json.dumps(report, indent=2))
    (ROOT / 'reports/latest_age_improvement.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'per_age'}, indent=2))


if __name__ == '__main__':
    main()
