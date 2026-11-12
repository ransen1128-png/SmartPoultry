"""Conservative ResNet-18 fine-tuning with unchanged verified labels and group splits."""
import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms
from improve_spur_age import score

ROOT = Path(__file__).resolve().parents[1]


def main():
    torch.set_num_threads(4)
    torch.manual_seed(2026)
    random.seed(2026)
    np.random.seed(2026)
    torch.use_deterministic_algorithms(True)
    source = ROOT / 'spur_age/experiments/20261109T074813049131Z/split_manifest.csv'
    rows = list(csv.DictReader(source.open(encoding='utf-8', newline='')))
    active = ROOT / 'spur_age/models/spur_age_model.pth'
    original_hash = hashlib.sha256(active.read_bytes()).hexdigest()
    checkpoint = torch.load(active, map_location='cpu', weights_only=True)
    model = models.resnet18(weights=None)
    model.fc = torch.nn.Linear(512, 1)
    model.load_state_dict(checkpoint['model_state_dict'])
    for parameter in model.parameters():
        parameter.requires_grad = False
    for module in (model.layer4, model.fc):
        for parameter in module.parameters():
            parameter.requires_grad = True
    prep = transforms.Compose([transforms.Resize((checkpoint['image_size'], checkpoint['image_size'])),
        transforms.ToTensor(), transforms.Normalize(checkpoint['normalization_mean'], checkpoint['normalization_std'])])
    images, ages = [], []
    group_splits = {}
    for row in rows:
        if row['age_verified'] != 'yes' or hashlib.sha256(Path(row['image']).read_bytes()).hexdigest() != row['sha256']:
            raise RuntimeError('Unverified or changed source')
        for key in ('pixel_sha256', 'source_family'):
            token = (key, row[key])
            if token in group_splits and group_splits[token] != row['split']:
                raise RuntimeError('Group leakage')
            group_splits[token] = row['split']
        with Image.open(row['image']) as image:
            images.append(prep(image.convert('RGB')))
        ages.append(float(row['age_months']))
    x = torch.stack(images)
    y = torch.tensor(ages)
    partitions = {name: [i for i, row in enumerate(rows) if row['split'] == name] for name in ('train', 'validation', 'test')}
    from collections import Counter
    families = Counter(rows[i]['source_family'] for i in partitions['train'])
    weights = torch.tensor([1/families[rows[i]['source_family']] for i in partitions['train']])
    sampler = torch.utils.data.WeightedRandomSampler(weights, len(partitions['train']), replacement=True)
    optimizer = torch.optim.AdamW([{'params': model.layer4.parameters(), 'lr': 1e-5},
                                  {'params': model.fc.parameters(), 'lr': 1e-4}], weight_decay=.01)
    model.eval()  # Freeze batch-normalization statistics on this small dataset.
    with torch.inference_mode():
        baseline = torch.cat([model(batch).flatten() for batch in x.split(8)]).clone()
    run = ROOT / 'spur_age/experiments' / ('finetune_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    run.mkdir(parents=True)
    best = float((baseline[partitions['validation']].clamp(1, 24)-y[partitions['validation']]).abs().mean())
    best_epoch, stale, history = 0, 0, []
    torch.save({**checkpoint, 'model_state_dict': model.state_dict()}, run / 'candidate.pth')
    for epoch in range(30):
        model.eval()
        sampled = [partitions['train'][i] for i in sampler]
        for start in range(0, len(sampled), 8):
            indices = sampled[start:start+8]
            batch = x[indices].clone()
            flip = torch.rand(len(indices)) < .5
            batch[flip] = batch[flip].flip(-1)
            optimizer.zero_grad()
            prediction = model(batch).flatten()
            loss = torch.nn.functional.smooth_l1_loss(prediction, y[indices], beta=1.)
            loss += .05*torch.nn.functional.mse_loss(prediction, baseline[indices])
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 2.)
            optimizer.step()
        with torch.inference_mode():
            val = model(x[partitions['validation']]).flatten().clamp(1, 24)
            mae = float((val-y[partitions['validation']]).abs().mean())
        history.append({'epoch': epoch+1, 'validation_mae': mae})
        print(f'Epoch {epoch+1}: validation MAE {mae:.4f}', flush=True)
        if mae < best:
            best, best_epoch, stale = mae, epoch+1, 0
            torch.save({**checkpoint, 'model_state_dict': model.state_dict(),
                        'validation_mae_months': mae, 'source_checkpoint_sha256': original_hash,
                        'evaluation_status': 'Source-family fine-tuning diagnostic; original pretraining overlap and bird identity unresolved.'}, run / 'candidate.pth')
        else:
            stale += 1
        if stale >= 8:
            break
    selected = torch.load(run / 'candidate.pth', map_location='cpu', weights_only=True)
    model.load_state_dict(selected['model_state_dict'])
    model.eval()
    with torch.inference_mode():
        predictions = torch.cat([model(batch).flatten() for batch in x.split(8)]).clamp(1, 24).numpy()
    baseline = baseline.numpy()
    y = y.numpy()
    report = {'run': str(run), 'best_epoch': best_epoch, 'history': history,
              'independence': 'Source-family split; original checkpoint trained with prior corpus overlap. Not independent-chicken validation.',
              'original_checkpoint_unchanged': hashlib.sha256(active.read_bytes()).hexdigest() == original_hash,
              'source_checkpoint_sha256': original_hash, 'seed': 2026, 'source_family_leakage': False}
    for name, indices in partitions.items():
        report[name] = {'original': score(y[indices], baseline[indices]), 'candidate': score(y[indices], predictions[indices])}
        report[name]['per_age'] = {
            str(age): {'original': score(y[ix], baseline[ix]), 'candidate': score(y[ix], predictions[ix])}
            for age in range(1, 25) if len(ix := np.array([i for i in indices if y[i] == age], dtype=int))}
    report['eligible_for_experimental_release'] = (
        report['validation']['candidate']['mae_months'] < report['validation']['original']['mae_months']-.05 and
        report['test']['candidate']['mae_months'] < report['test']['original']['mae_months']-.05)
    report['per_age'] = {str(age): {'original': score(y[ix], baseline[ix]), 'candidate': score(y[ix], predictions[ix])}
                         for age in range(1, 25) if len(ix := np.flatnonzero(y == age))}
    with (run / 'predictions.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['image','sha256','source_family','split','age_months','original_prediction','candidate_prediction'])
        writer.writeheader()
        for i, row in enumerate(rows):
            writer.writerow({**{key: row[key] for key in ('image','sha256','source_family','split','age_months')},
                             'original_prediction': float(np.clip(baseline[i],1,24)), 'candidate_prediction': float(predictions[i])})
    selected['test_mae_months'] = report['test']['candidate']['mae_months']
    torch.save(selected, run / 'candidate.pth')
    (run / 'report.json').write_text(json.dumps(report, indent=2))
    (ROOT / 'reports/latest_age_finetuning.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('per_age','history')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
