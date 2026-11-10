"""Train/evaluate separate real annotation models. Never touch the age model."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('task', choices=['detect', 'segment'])
    parser.add_argument('--epochs', type=int, default=45)
    parser.add_argument('--freeze', type=int, default=10)
    parser.add_argument('--initial-optimizer-settings', action='store_true',
                        help='Reproduce the executed first segmentation run (use with --freeze 0).')
    args = parser.parse_args()
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    torch.set_num_threads(4)
    from ultralytics import YOLO
    import ultralytics.utils.torch_utils as torch_utils
    torch_utils.NUM_THREADS = 4
    age_path = ROOT / 'spur_age/models/spur_age_model.pth'
    age_hash = hashlib.sha256(age_path.read_bytes()).hexdigest()
    initial = ROOT / ('yolo11n.pt' if args.task == 'detect' else 'yolo11n-seg.pt')
    model = YOLO(str(initial))
    data = ROOT / 'detection/derived' / args.task / 'data.yaml'
    trained = model.train(data=str(data), epochs=args.epochs, imgsz=512, batch=4,
                          device='cpu', workers=0, seed=2026, deterministic=True,
                          project=str(ROOT / 'detection/runs'), name=f'anatomy_{args.task}',
                          exist_ok=False, patience=15, pretrained=True, optimizer='AdamW',
                          lr0=.001, lrf=.1, cos_lr=True, amp=False, cache='ram',
                          freeze=args.freeze,
                          nbs=64 if args.initial_optimizer_settings else 4,
                          warmup_bias_lr=.1 if args.initial_optimizer_settings else .001,
                          warmup_epochs=3 if args.initial_optimizer_settings else 2,
                          mosaic=.5, close_mosaic=10, degrees=8, translate=.1,
                          scale=.3, fliplr=.5, plots=True, save=True)
    run = Path(model.trainer.save_dir)
    best = run / 'weights/best.pt'
    selected = YOLO(str(best))
    metrics = {}
    for split in ('val', 'test'):
        result = selected.val(data=str(data), split=split, imgsz=512, batch=4,
                              device='cpu', workers=0, plots=True, project=str(run), name=f'{split}_evaluation')
        metrics[split] = {str(k): float(v) for k, v in result.results_dict.items()}
    if hashlib.sha256(age_path.read_bytes()).hexdigest() != age_hash:
        raise RuntimeError('Age model changed unexpectedly')
    report = {'task': args.task, 'checkpoint': str(best), 'run': str(run),
              'metrics': metrics, 'age_checkpoint_unchanged': True,
              'annotation_summary': json.loads((ROOT / 'detection/annotation_summary.json').read_text()),
              'status': 'experimental_candidate_executed',
              'limitation': 'Source-family holdouts; actual bird identity unresolved. Assistant visual annotations are not independent expert verification.'}
    (run / 'evaluation.json').write_text(json.dumps(report, indent=2))
    (ROOT / 'detection' / f'latest_{args.task}.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
