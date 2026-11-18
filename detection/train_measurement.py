"""Train separate experimental endpoint/outline candidates; never auto-promote."""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def age_fingerprints():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/'spur_age').rglob('*.pth')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task',choices=['pose','segment'])
    parser.add_argument('--dataset',type=Path,default=ROOT/'detection/derived/measurement_v1')
    parser.add_argument('--epochs',type=int,default=50)
    parser.add_argument('--allow-assistant-labels',action='store_true')
    parser.add_argument('--run-name',help='New version name; existing candidate folders are preserved.')
    args=parser.parse_args()
    run_name=args.run_name or f'measurement_{args.task}_v1'
    if Path(run_name).name!=run_name or run_name in ('.','..'):
        raise ValueError('Use a single new folder name for --run-name.')
    if (ROOT/'detection/runs'/run_name).exists():
        raise ValueError('Candidate folder already exists. Choose a new --run-name; no checkpoint was overwritten.')
    report=json.loads((args.dataset/'manifest.json').read_text())
    if report.get('label_provenance')!='human_reviewed' and not report['independent_annotation_verification'] and not args.allow_assistant_labels:
        raise ValueError('Independent label verification pending; explicitly opt into an experimental candidate.')
    before=age_fingerprints()
    os.environ['YOLO_AUTOINSTALL']='false';os.environ['WANDB_MODE']='disabled';os.environ['OMP_NUM_THREADS']='4'
    import torch
    torch.set_num_threads(4)
    from ultralytics import YOLO
    from ultralytics.utils import torch_utils
    torch_utils.NUM_THREADS=4
    if args.task=='pose':
        initial=ROOT/'.cache-huggingface/measurement-init/yolo11n-pose.pt'
        initial.parent.mkdir(parents=True,exist_ok=True)
    else:
        manifest=json.loads((ROOT/'ml_models/poultry_vision/manifest.json').read_text())
        initial=ROOT/'ml_models/poultry_vision'/manifest['segment']['filename']
    model=YOLO(str(initial))
    model.train(data=str(args.dataset/args.task/'data.yaml'),epochs=args.epochs,imgsz=512,batch=2,
                device='cpu',workers=0,seed=20261116,deterministic=True,project=str(ROOT/'detection/runs'),
                name=run_name,exist_ok=False,patience=15,optimizer='AdamW',
                lr0=.0003,lrf=.1,cos_lr=True,amp=False,cache=False,freeze=0,nbs=2,
                warmup_bias_lr=.001,warmup_epochs=2,mosaic=.35,close_mosaic=8,
                degrees=12,translate=.1,scale=.4,fliplr=.5,plots=True)
    run=Path(model.trainer.save_dir)
    candidate=YOLO(str(run/'weights/best.pt'))
    metrics={}
    for split in ('val','test'):
        result=candidate.val(data=str(args.dataset/args.task/'data.yaml'),split=split,imgsz=512,batch=1,
                             device='cpu',workers=0,plots=True,project=str(run),name=f'{split}_evaluation')
        metrics[split]={str(k):float(v) for k,v in result.results_dict.items()}
    if age_fingerprints()!=before:
        raise RuntimeError('An age checkpoint changed during candidate training')
    output={'task':args.task,'status':'executed_experimental_candidate','deployed':False,
            'dataset':str(args.dataset),'checkpoint':str(run/'weights/best.pt'),'metrics':metrics,
            'age_models_unchanged':True,'age_fingerprints':before,
            'label_provenance':report.get('label_provenance','assistant_visual_review'),
            'independent_annotation_verification':report.get('independent_annotation_verification',False),
            'limitation':'Source-family holdouts and unresolved animal identities. No claim of exact anatomical endpoints or physical length; review annotation provenance in the dataset manifest.'}
    (run/'measurement_evaluation.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))


if __name__=='__main__':main()
