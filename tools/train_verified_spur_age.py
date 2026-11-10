"""Reproducible image-only candidate training after human identity/age review.

Does not modify originals, the active checkpoint or the review queue. Uses
real ImageNet features and verified existing ages, never filename features.
"""
import argparse
import csv
import hashlib
import json
import random
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import torch
import numpy as np

from audit_spur_dataset import digest, write_csv


ROOT = Path(__file__).resolve().parents[1]


def load_review(path, content_family_experiment=False):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    errors, hashes = [], set()
    for i, row in enumerate(rows, 2):
        try:
            age = float(row['age_months'])
            if not np.isfinite(age) or not 1 <= age <= 24:
                raise ValueError
        except (KeyError, ValueError):
            errors.append(f'row {i}: age must be an existing verified value in 1-24 months')
        for key in ('chicken_id', 'source_family', 'record_reference'):
            if not row.get(key, '').strip():
                errors.append(f'row {i}: missing reviewed {key}')
        for key in (('age_verified',) if content_family_experiment else ('identity_verified', 'age_verified')):
            if row.get(key, '').strip().lower() != 'yes':
                errors.append(f'row {i}: {key} is not yes')
        allowed_content = {'spur_closeup', 'leg_closeup', 'mixed_unlocalized'} if content_family_experiment else {'spur_closeup', 'leg_closeup'}
        if row.get('content_type') not in allowed_content:
            errors.append(f'row {i}: select a reviewed spur_closeup or leg_closeup for this age model')
        image_path = Path(row.get('image', ''))
        if not image_path.is_file():
            errors.append(f'row {i}: missing image')
        elif digest(image_path) != row.get('sha256'):
            errors.append(f'row {i}: image changed since audit')
        pixel_hash = row.get('pixel_sha256', '')
        if not pixel_hash or pixel_hash in hashes:
            errors.append(f'row {i}: duplicate or absent decoded-pixel hash')
        hashes.add(pixel_hash)
    if not rows:
        errors.append('Review manifest contains no photographs')
    if errors:
        raise ValueError(f'{len(errors)} unresolved review checks. First issues: ' + '; '.join(errors[:10]))
    return rows


def group_components(rows):
    # Union both persistent bird IDs and derivative/session families.
    parents = list(range(len(rows)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    owners = {}
    for i, row in enumerate(rows):
        for key in ('chicken_id', 'source_family', 'pixel_sha256'):
            token = (key, row[key].strip())
            if token in owners:
                parents[find(i)] = find(owners[token])
            else:
                owners[token] = i
    return [find(i) for i in range(len(rows))]


def create_splits(rows, seed):
    from sklearn.model_selection import GroupShuffleSplit
    groups = np.array(group_components(rows))
    if len(set(groups)) < 7:
        raise ValueError('Need at least seven verified independent bird/source groups for train/validation/test.')
    train_val, test = next(GroupShuffleSplit(n_splits=1, test_size=.15, random_state=seed).split(rows, groups=groups))
    train_rel, val_rel = next(GroupShuffleSplit(n_splits=1, test_size=.15/.85, random_state=seed + 1)
                              .split(train_val, groups=groups[train_val]))
    splits = {'train': train_val[train_rel].tolist(), 'validation': train_val[val_rel].tolist(), 'test': test.tolist()}
    seen = {}
    for split, indices in splits.items():
        for i in indices:
            if groups[i] in seen and seen[groups[i]] != split:
                raise RuntimeError('Bird/source group leakage')
            seen[groups[i]] = split
    return splits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--review', type=Path, default=ROOT / 'reports/dataset_audit/review_queue.csv')
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--content-family-experiment', action='store_true',
                        help='Train/evaluate on conservative visual families, explicitly without claiming verified bird independence.')
    args = parser.parse_args()
    try:
        if args.content_family_experiment and args.review == ROOT / 'reports/dataset_audit/review_queue.csv':
            args.review = ROOT / 'reports/dataset_audit/visual_family_manifest.csv'
        rows = load_review(args.review, args.content_family_experiment)
        # A supplied review cannot invent new image hashes or silently change age labels.
        original = list(csv.DictReader((ROOT / 'reports/dataset_audit/image_inventory.csv').open(encoding='utf-8', newline='')))
        audited = {r['sha256']: r for r in original if r.get('metadata_rows') == '1' and not r['error']}
        for row in rows:
            known = audited.get(row['sha256'])
            if (not known or row['pixel_sha256'] != known['pixel_sha256']
                    or float(row['age_months']) != float(known['age_months'])):
                raise ValueError('Review row does not match audited existing pixels and age labels; re-audit documented corrections first.')
        splits = create_splits(rows, args.seed)
        if args.content_family_experiment:
            membership = {rows[i]['pixel_sha256']: split for split, indices in splits.items() for i in indices}
            pairs = list(csv.DictReader((ROOT / 'reports/dataset_audit/near_duplicate_pairs.csv').open(encoding='utf-8', newline='')))
            for pair in pairs:
                if pair['grouped'] == 'True' and membership[pair['hash_a']] != membership[pair['hash_b']]:
                    raise ValueError('Detected near-duplicate pair crosses split boundaries')
    except (ValueError, KeyError) as exc:
        destination = ROOT / 'reports/dataset_audit/training_readiness.json'
        destination.write_text(json.dumps({'status': 'blocked_by_unverified_records', 'reason': str(exc),
                                           'training_executed': False}, indent=2), encoding='utf-8')
        parser.exit(2, f'Training not started: {exc}\n')
    if args.check_only:
        print(json.dumps({'status': 'ready', 'images': len(rows), 'splits': {k: len(v) for k, v in splits.items()}}))
        return
    if args.epochs < 1:
        parser.error('--epochs must be positive')
    import torchvision
    from PIL import Image
    from torchvision import models, transforms
    from evaluate_existing_age_model import metrics
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    active = ROOT / 'spur_age/models/spur_age_model.pth'
    active_hash = digest(active)
    backup = active.parent / 'backups' / f'resnet18_{active_hash}.pth'
    backup.parent.mkdir(exist_ok=True)
    if not backup.exists():
        shutil.copy2(active, backup)
    if digest(backup) != active_hash:
        raise RuntimeError('Existing checkpoint backup verification failed')
    run = ROOT / 'spur_age/experiments' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True, exist_ok=False)
    manifest = [{**rows[i], 'split': split} for split, indices in splits.items() for i in indices]
    write_csv(run / 'split_manifest.csv', manifest)
    configuration = {'seed': args.seed, 'epochs': args.epochs, 'review_sha256': digest(args.review),
                     'active_checkpoint_sha256': active_hash, 'torch': str(torch.__version__),
                     'torchvision': str(torchvision.__version__), 'optimizer': 'Adam lr=0.01',
                     'loss': 'L1', 'frozen_imagenet_features': True,
                     'split_manifest_sha256': digest(run / 'split_manifest.csv')}
    configuration['independence'] = ('visual_family_holdout_bird_identity_unresolved' if args.content_family_experiment
                                   else 'reviewed_bird_and_source_group_holdout')
    configuration['training_weighting'] = 'Inverse training-family image count, so long near-duplicate sequences do not dominate.'
    (run / 'configuration.json').write_text(json.dumps(configuration, indent=2))
    mean, std = [.485, .456, .406], [.229, .224, .225]
    transform = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(), transforms.Normalize(mean, std)])
    backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    backbone.fc = torch.nn.Identity()
    backbone.eval()  # frozen batch-normalization statistics as well as parameters
    features = []
    with torch.inference_mode():
        for row in rows:
            with Image.open(row['image']) as image:
                features.append(backbone(transform(image.convert('RGB')).unsqueeze(0)).squeeze(0))
    x = torch.stack(features).clone()
    y = torch.tensor([float(r['age_months']) for r in rows]).reshape(-1, 1)
    family_sizes = defaultdict(int)
    for i in splits['train']:
        family_sizes[rows[i]['source_family']] += 1
    sample_weights = torch.tensor([1. / max(1, family_sizes[r['source_family']]) for r in rows])
    head = torch.nn.Linear(512, 1)
    optimizer = torch.optim.Adam(head.parameters(), lr=.01)
    best, history = float('inf'), []
    for epoch in range(args.epochs):
        head.train()
        shuffled = torch.tensor(splits['train'])[torch.randperm(len(splits['train']))]
        for indices in shuffled.split(16):
            optimizer.zero_grad()
            losses = (head(x[indices]) - y[indices]).abs().flatten()
            loss = (losses * sample_weights[indices]).sum() / sample_weights[indices].sum()
            loss.backward()
            optimizer.step()
        head.eval()
        with torch.no_grad():
            validation_mae = (head(x[splits['validation']]).clamp(1, 24) - y[splits['validation']]).abs().mean().item()
        history.append({'epoch': epoch + 1, 'validation_mae_months': validation_mae})
        if validation_mae < best:
            best = validation_mae
            backbone.fc = head
            torch.save({'model_state_dict': backbone.state_dict(), 'architecture': 'resnet18',
                        'age_min': 1, 'age_max': 24, 'image_size': 224,
                        'normalization_mean': mean, 'normalization_std': std,
                        'validation_mae_months': best, 'seed': args.seed,
                        'split_manifest_sha256': configuration['split_manifest_sha256'],
                        'evaluation_status': 'candidate_not_promoted',
                        'independence': configuration['independence']}, run / 'candidate.pth')
            backbone.fc = torch.nn.Identity()
    write_csv(run / 'validation_history.csv', history)
    (run / 'split_checks.json').write_text(json.dumps({
        'exact_pixel_groups_crossing_splits': 0,
        'detected_near_duplicate_pairs_crossing_splits': 0,
        'source_families_crossing_splits': 0,
        'recorded_chicken_ids_crossing_splits': 0,
        'actual_bird_identity_independence': 'unresolved' if args.content_family_experiment else 'reviewed',
        'all_distinct_audited_images_used': len(rows) == len(audited),
    }, indent=2))
    candidate = torch.load(run / 'candidate.pth', map_location='cpu', weights_only=True)
    trained = models.resnet18(weights=None)
    trained.fc = torch.nn.Linear(512, 1)
    trained.load_state_dict(candidate['model_state_dict'])
    trained.eval()
    old = torch.load(active, map_location='cpu', weights_only=True)
    baseline = models.resnet18(weights=None)
    baseline.fc = torch.nn.Linear(512, 1)
    baseline.load_state_dict(old['model_state_dict'])
    baseline.eval()
    old_transform = transforms.Compose([
        transforms.Resize((old['image_size'], old['image_size'])), transforms.ToTensor(),
        transforms.Normalize(old['normalization_mean'], old['normalization_std'])])
    comparison = {}
    for name, model, prep in [('candidate', trained, transform), ('existing', baseline, old_transform)]:
        for split in ('validation', 'test'):
            outputs = []
            with torch.inference_mode():
                for i in splits[split]:
                    with Image.open(rows[i]['image']) as image:
                        prediction = model(prep(image.convert('RGB')).unsqueeze(0)).item()
                    outputs.append({'image': rows[i]['image'], 'age_months': float(rows[i]['age_months']),
                                    'prediction_months': max(1., min(24., prediction)),
                                    'error_months': max(1., min(24., prediction)) - float(rows[i]['age_months']),
                                    'absolute_error_months': abs(max(1., min(24., prediction)) - float(rows[i]['age_months']))})
            write_csv(run / f'{name}_{split}_predictions.csv', outputs)
            write_csv(run / f'{name}_{split}_per_age.csv', (
                {'age_months': age, **metrics([r for r in outputs if r['age_months'] == age])} for age in range(1, 25)))
            write_csv(run / f'{name}_{split}_per_group.csv', (
                {'age_group': f'{lo}-{lo+5}', **metrics([r for r in outputs if lo <= r['age_months'] <= lo+5])} for lo in (1, 7, 13, 19)))
            write_csv(run / f'{name}_{split}_confusion.csv', (
                {'actual_age': age, **{f'predicted_{p}': sum(int(r['age_months']) == age and
                    int(np.floor(r['prediction_months']+.5)) == p for r in outputs) for p in range(1, 25)}} for age in range(1, 25)))
            comparison[f'{name}_{split}'] = metrics(outputs)
    comparison['selection'] = 'No automatic promotion; existing-model training overlap is unknown.'
    comparison['independence'] = configuration['independence']
    comparison['candidate_selected_by'] = 'Lowest validation MAE, never test MAE'
    comparison['original_checkpoint_unchanged'] = digest(active) == active_hash
    comparison['split_counts'] = {key: len(value) for key, value in splits.items()}
    training_median = float(np.median([float(rows[i]['age_months']) for i in splits['train']]))
    comparison['constant_training_median_months'] = training_median
    for split in ('validation', 'test'):
        comparison[f'constant_median_{split}'] = metrics([
            {'age_months': float(rows[i]['age_months']), 'prediction_months': training_median}
            for i in splits[split]])
    comparison['limitation'] = 'Existing-model scores may include prior training images; not an independent baseline comparison.'
    (run / 'comparison.json').write_text(json.dumps(comparison, indent=2))
    candidate['test_mae_months'] = comparison['candidate_test']['mae_months']
    torch.save(candidate, run / 'candidate.pth')
    if digest(active) != active_hash:
        raise RuntimeError('Active checkpoint unexpectedly changed')
    (ROOT / 'reports/dataset_audit/training_readiness.json').write_text(json.dumps({
        'status': 'content_family_candidate_trained' if args.content_family_experiment else 'reviewed_candidate_trained',
        'training_executed': True, 'run': str(run),
        'independence': configuration['independence'], 'active_model_replaced': False,
    }, indent=2))
    print(f'Candidate trained and evaluated in {run}; original model unchanged.')


if __name__ == '__main__':
    main()
