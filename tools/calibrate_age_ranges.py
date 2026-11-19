"""Calibrate prediction ranges on verified unseen birds; test on other birds.

Consumes evaluate_unseen_chickens.py's report. Does not train or change weights.
Minimum 20 calibration and 20 test chickens. Group maxima make all photographs
of each calibration bird one unit. Test birds never determine the range width.
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path


def calibrate(report,coverage=.9):
    if not report.get('independent_evaluation_executed') or not report.get('provenance_sha256'):
        raise ValueError('Verified unseen-chicken evaluation and provenance are required.')
    birds={}
    for row in report.get('predictions',[]):
        age=float(row['age_months']);prediction=float(row['prediction_months'])
        if not math.isfinite(age) or not math.isfinite(prediction) or not 1<=age<=24 or not 1<=prediction<=24:
            raise ValueError('Ages and predictions must be finite and within 1-24 months.')
        if not row['chicken_id']:raise ValueError('Persistent chicken IDs are required.')
        birds.setdefault(row['chicken_id'],[]).append(abs(age-prediction))
    ids=sorted(birds);random.Random(2026).shuffle(ids)
    split=len(ids)//2;calibration,test=ids[:split],ids[split:]
    if min(len(calibration),len(test))<20:
        raise ValueError('At least 40 verified unseen chickens are required: 20 calibration and 20 separate test birds.')
    errors=sorted(max(birds[bird]) for bird in calibration)
    rank=math.ceil((len(errors)+1)*coverage)
    if rank>len(errors):raise ValueError('Not enough calibration birds for the selected coverage.')
    radius=errors[rank-1]
    observed=sum(max(birds[bird])<=radius for bird in test)/len(test)
    return {'status':'tested','checkpoint_sha256':report['checkpoint_sha256'],'target_coverage':coverage,
        'radius_months':radius,'calibration_chickens':len(calibration),'test_chickens':len(test),
        'held_out_bird_coverage':observed,'calibration_ids':calibration,'test_ids':test,
        'method':'split conformal; bird-wise maximum absolute error; fixed seed 2026',
        'limitation':'Coverage assumes comparable independent chickens. Human identity and training-exclusion attestation is required.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    root=Path(__file__).resolve().parents[1]
    parser.add_argument('--report',type=Path,default=root/'reports/unseen_evaluation/report.json')
    parser.add_argument('--output',type=Path,default=root/'reports/unseen_evaluation/intervals.json')
    args=parser.parse_args()
    try:
        content=args.report.read_bytes();result=calibrate(json.loads(content))
        result['evaluation_sha256']=hashlib.sha256(content).hexdigest()
    except (OSError,ValueError,KeyError,TypeError) as error:
        result={'status':'unavailable','reason':str(error),'tested_range_available':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if not key.endswith('_ids')},indent=2))
    return 0 if result['status']=='tested' else 2


if __name__=='__main__':raise SystemExit(main())
