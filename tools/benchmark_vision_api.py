"""Compare current age model with API-localized crops. Never auto-promote."""
import argparse
import csv
import hashlib
import json
import os
import sys
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))
load_dotenv(ROOT/'.env',override=False)
from core.vision_api import locate_spurs,crop_visible_spur,PROMPT_HASH


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--split',choices=['validation','test'],default='validation')
    parser.add_argument('--api-model',help='Explicit experiment model; does not change .env or live app.')
    args=parser.parse_args()
    out=ROOT/'reports/vision_api';out.mkdir(exist_ok=True)
    if not (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')) or not os.environ.get('GEMINI_VISION_MODEL'):
        report={'status':'blocked_missing_credentials','accuracy_comparison_executed':False,
                'required_environment':['GEMINI_API_KEY','GEMINI_VISION_MODEL'], 'live_app_unchanged':True}
        (out/'readiness.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));return 2
    model=args.api_model or os.environ['GEMINI_VISION_MODEL']
    from core.age_model_registry import candidate_entry
    variant='finetuned' if candidate_entry() else 'original'
    from core.rooster_age_classifier import predict_rooster_age
    all_rows=list(csv.DictReader((ROOT/'spur_age/experiments/20261109T074813049131Z/split_manifest.csv').open(encoding='utf-8',newline='')))
    grouped={}
    for row in all_rows:
        for field in ('source_family','pixel_sha256'):
            token=(field,row[field])
            if token in grouped and grouped[token]!=row['split']:raise RuntimeError('Split leakage')
            grouped[token]=row['split']
    checkpoint_hash=(candidate_entry()['sha256'] if variant=='finetuned' else hashlib.sha256((ROOT/'spur_age/models/spur_age_model.pth').read_bytes()).hexdigest())
    if args.split=='test':
        validation=json.loads((out/'validation.json').read_text())
        if not (validation['status']=='complete' and validation['api_crop_mae_months']<validation['baseline_mae_months'] and validation['api_model']==model and validation['prompt_sha256']==PROMPT_HASH and validation['checkpoint_sha256']==checkpoint_hash):
            raise RuntimeError('Run a complete, improved validation comparison first; do not tune on test results.')
    rows=[row for row in all_rows if row['split']==args.split]
    results=[]
    cache=out/'cache';cache.mkdir(exist_ok=True)
    for index,row in enumerate(rows):
        path=Path(row['image'])
        if row['age_verified']!='yes' or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Unverified/changed source')
        with Image.open(path) as raw:image=ImageOps.exif_transpose(raw).convert('RGB')
        stream=BytesIO();image.save(stream,format='PNG');stream.seek(0)
        baseline=predict_rooster_age(stream,model_variant=variant)
        if baseline is None:raise RuntimeError('Current model could not predict')
        cache_key=hashlib.sha256((row['sha256']+model+PROMPT_HASH).encode()).hexdigest()
        cached=cache/(cache_key+'.json')
        api=json.loads(cached.read_text()) if cached.exists() else locate_spurs(image,model=model,max_attempts=1)
        if api['status']=='completed':cached.write_text(json.dumps(api,indent=2))
        crop=crop_visible_spur(image,api['boxes']) if api['status']=='completed' else None
        proposed=baseline
        if crop is not None:
            stream=BytesIO();crop.save(stream,format='PNG');stream.seek(0)
            proposed=predict_rooster_age(stream,model_variant=variant)
            if proposed is None:raise RuntimeError('Crop inference failed')
        results.append({'source_sha256':row['sha256'],'source_family':row['source_family'],'verified_age_months':float(row['age_months']),
                        'baseline_prediction':baseline['age_months'],'api_crop_prediction':proposed['age_months'],
                        'used_crop':crop is not None,'api':api})
        (out/'progress.json').write_text(json.dumps({'split':args.split,'api_model':model,'completed':len(results),'planned':len(rows),'results':results},indent=2))
        print(f'{index+1}/{len(rows)}: {api["status"]}',flush=True)
        if api['status']!='completed':
            print('Stopping comparison on API failure; no improvement claimed.',flush=True)
            break
    baseline=sum(abs(r['baseline_prediction']-r['verified_age_months']) for r in results)/len(results)
    measured=sum(abs(r['api_crop_prediction']-r['verified_age_months']) for r in results)/len(results)
    errors=sum(r['api']['status']!='completed' for r in results)
    crops=sum(r['used_crop'] for r in results)
    report={'status':'complete' if not errors and crops and len(results)==len(rows) else 'incomplete_or_no_crops','split':args.split,'n':len(results),
        'api_model':model,'prompt_sha256':PROMPT_HASH,'checkpoint_sha256':checkpoint_hash,'age_model':variant,
        'baseline_mae_months':baseline,'api_crop_mae_months':measured,'relative_error_reduction_percent':100*(baseline-measured)/baseline if baseline and not errors and crops and len(results)==len(rows) else None,
        'api_errors':errors,'crops_used':crops,'fixed_policy':'Largest spur box with 15% padding; full-image fallback when no box/error',
        'limitation':'Source-family comparison only. Prior age-model training overlap and unresolved bird identities prevent independent accuracy claims. API boxes are not ground truth.',
        'deployed':False,'results':results}
    (out/(args.split+'.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
    return 0


if __name__=='__main__':sys.exit(main())
