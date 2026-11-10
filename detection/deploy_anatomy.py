"""Activate separately trained experimental checkpoints after validation-only calibration."""
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]


def main():
    from ultralytics import YOLO
    torch.set_num_threads(4)
    destination = ROOT / 'ml_models/poultry_vision'
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'version': datetime.now(timezone.utc).isoformat(), 'experimental': True,
                'limitations': 'Small source-family holdouts; bird identity unresolved. Assistant annotations require expert review.'}
    for task in ('detect', 'segment'):
        report = json.loads((ROOT / f'detection/latest_{task}.json').read_text())
        checkpoint = Path(report['checkpoint'])
        model = YOLO(str(checkpoint))
        expected = {0: 'leg', 1: 'spur'} if task == 'detect' else {0: 'spur'}
        if model.names != expected:
            raise ValueError('Unexpected class schema')
        validation = model.val(data=str(ROOT / f'detection/derived/{task}/data.yaml'),
                               split='val', imgsz=512, batch=4, device='cpu', workers=0,
                               plots=False, project=str(ROOT / 'detection/runs'), name=f'{task}_calibration')
        metric = validation.box if task == 'detect' else validation.seg
        curve = np.asarray(metric.f1_curve).mean(axis=0)
        best = int(np.argmax(np.convolve(curve, np.ones(21)/21, mode='same')))
        threshold = float(np.clip(metric.px[best], .05, .75))
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        filename = f'{task}_{digest[:16]}.pt'
        shutil.copy2(checkpoint, destination / filename)
        manifest[task] = {'filename': filename, 'sha256': digest, 'threshold': threshold,
                          'threshold_source': 'Maximum smoothed mean F1 on validation only',
                          'metrics': report['metrics'], 'training_report': str(Path(report['run']) / 'evaluation.json')}
    temporary = destination / 'manifest.pending.json'
    temporary.write_text(json.dumps(manifest, indent=2))
    os.replace(temporary, destination / 'manifest.json')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
