"""Compare current and candidate outlines on the same held-out source images."""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,default=ROOT/'detection/derived/measurement_v1')
    parser.add_argument('--segment-run',type=Path,default=ROOT/'detection/runs/measurement_segment_v1')
    args=parser.parse_args()
    os.environ['OMP_NUM_THREADS']='2'
    import torch
    torch.set_num_threads(2)
    from ultralytics import YOLO
    from ultralytics.utils.metrics import smooth
    manifest=json.loads((ROOT/'ml_models/poultry_vision/manifest.json').read_text())
    original=ROOT/'ml_models/poultry_vision'/manifest['segment']['filename']
    candidate=args.segment_run/'weights/best.pt';report={}
    for label,path,splits in (('baseline',original,('val','test')),('candidate',candidate,('val','test'))):
        model=YOLO(str(path))
        for split in splits:
            result=model.val(data=str(args.dataset/'segment/data.yaml'),split=split,imgsz=512,batch=1,
                device='cpu',workers=0,plots=False,project=str(args.segment_run),name=f'compare_{label}_{split}',exist_ok=False,verbose=False)
            metrics=result.seg;index=int(smooth(metrics.f1_curve.mean(0),.1).argmax())
            report[label+'_'+split]={'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'metrics':{str(k):float(v) for k,v in result.results_dict.items()},
                'mask_confidence_threshold':float(metrics.px[index])}
            (args.segment_run/'baseline_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
