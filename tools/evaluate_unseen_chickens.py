"""Read-only independent evaluation gate; never trains or replaces a model.

CSV fields: image,age_months,chicken_id,age_verified,identity_verified,
not_in_training_verified,record_reference. Verification fields must be 'yes'.
References must identify an actual age/identity and training-membership record.
"""
import argparse
import csv
import hashlib
import json
import sys
import random
from datetime import datetime,timezone
from pathlib import Path
from collections import Counter
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
from audit_spur_dataset import inspect, EXTENSIONS


def validate(rows, known, base):
    issues, accepted, seen = [], [], set()
    hashes = {r['sha256'] for r in known}
    pixels = {r['pixel_sha256'] for r in known}
    dhashes = {int(r['dhash'], 16) for r in known if r.get('dhash')}
    for number, row in enumerate(rows, 2):
        reasons = []
        path = Path(row.get('image', ''))
        if not path.is_absolute(): path = base / path
        if not path.is_file():
            issues.append({'line': number, 'reasons': ['Missing image file']}); continue
        image = inspect(path)
        if image['error']: reasons.append('Image cannot be decoded')
        if image['sha256'] in hashes or image['pixel_sha256'] in pixels:
            reasons.append('Identical training-corpus image; cannot be an unseen test')
        elif image['dhash'] and any((int(image['dhash'], 16) ^ h).bit_count() <= 6 for h in dhashes):
            reasons.append('Visual similarity requires provenance review before independent testing')
        if image['pixel_sha256'] in seen: reasons.append('Duplicate within evaluation set')
        seen.add(image['pixel_sha256'])
        try:
            age = float(row.get('age_months', ''))
            if not 1 <= age <= 24: raise ValueError()
        except ValueError:
            age = None; reasons.append('Age must be verified and within 1-24 months')
        for field in ('age_verified', 'identity_verified', 'not_in_training_verified'):
            if row.get(field) != 'yes': reasons.append(f'{field} must be yes with supporting records')
        if not row.get('chicken_id', '').strip() or not row.get('record_reference', '').strip():
            reasons.append('Persistent chicken ID and provenance reference are required')
        if reasons: issues.append({'line': number, 'image': str(path), 'reasons': reasons})
        else: accepted.append({**row, **image, 'age_months': age})
    # Near-identical evaluation frames are also blocked, rather than inflated as independent samples.
    for i, row in enumerate(accepted):
        if any((int(row['dhash'], 16) ^ int(other['dhash'], 16)).bit_count() <= 6 for other in accepted[:i]):
            issues.append({'image': row['path'], 'reasons': ['Near-identical evaluation frames need review']})
    return accepted, issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--provenance',type=Path,help='Existing capture/identity register supporting the manifest. Its digest is saved; verification still requires human review.')
    parser.add_argument('--output', type=Path, default=ROOT/'reports/unseen_evaluation')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (ROOT/'reports/dataset_audit/image_inventory.csv').open(encoding='utf-8', newline='') as f:
        known = [r for r in csv.DictReader(f) if r.get('age_months') and not r['error']]
    report = {'independent_evaluation_executed': False, 'source_images_unchanged': True,
              'generated_utc':datetime.now(timezone.utc).isoformat(), 'seed':2026,
              'known_distinct_photos': len({r['pixel_sha256'] for r in known}),
              'limitation': 'Hash screening cannot establish chicken identity. Provenance requires human confirmation against training history.'}
    if args.manifest is None:
        sources = [inspect(p) for p in (ROOT/'spurs images').rglob('*') if p.suffix.lower() in EXTENSIONS]
        known_pixels = {r['pixel_sha256'] for r in known}
        report.update(status='blocked_no_verified_unseen_manifest', existing_source_files=len(sources),
                      existing_source_files_already_in_corpus=sum(r['pixel_sha256'] in known_pixels for r in sources),
                      missing=['Verified persistent chicken identities and ages for photographs outside all prior training',
                               'Capture/register references confirming those chickens were not in prior training'])
        with (args.output/'manifest_template.csv').open('w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(['image','age_months','chicken_id','age_verified','identity_verified','not_in_training_verified','record_reference'])
    else:
        manifest_hash=hashlib.sha256(args.manifest.read_bytes()).hexdigest()
        with args.manifest.open(encoding='utf-8-sig', newline='') as f: rows = list(csv.DictReader(f))
        accepted, issues = validate(rows, known, args.manifest.resolve().parent)
        if args.provenance is None or not args.provenance.is_file():
            issues.append({'reasons':['Provide --provenance pointing to the existing age/identity/capture register supporting the manifest.']})
        report.update(status='blocked_manifest_review', rows=len(rows), issues=issues)
        if rows and not issues:
            from core.rooster_age_classifier import predict_rooster_age
            from core.age_model_registry import candidate_entry
            from evaluate_existing_age_model import metrics
            selected_entry=candidate_entry()
            selected_path=selected_entry['resolved_path'] if selected_entry else ROOT/'spur_age/models/spur_age_model.pth'
            checkpoint_hash=hashlib.sha256(selected_path.read_bytes()).hexdigest()
            if selected_entry and checkpoint_hash!=selected_entry['sha256']:raise RuntimeError('Checkpoint differs from its registered checksum')
            predictions = []
            for row in accepted:
                content=Path(row['path']).read_bytes()
                if hashlib.sha256(content).hexdigest()!=row['sha256']:raise RuntimeError('Image changed after validation')
                result = predict_rooster_age(BytesIO(content), model_variant='finetuned' if selected_entry else 'original')
                if result is None: raise RuntimeError('Inference failed; no evaluation success recorded')
                predictions.append({'chicken_id':row['chicken_id'], 'sha256':row['sha256'],
                    'age_months':row['age_months'], 'prediction_months':result['age_months']})
            report.update(status='completed_with_provenance_attestation', independent_evaluation_executed=True,
                metrics=metrics(predictions), distinct_chickens=len({r['chicken_id'] for r in predictions}),
                chicken_balanced_mae_months=sum(sum(abs(r['prediction_months']-r['age_months']) for r in predictions if r['chicken_id']==chicken)/n
                    for chicken,n in Counter(r['chicken_id'] for r in predictions).items())/len({r['chicken_id'] for r in predictions}),
                per_age={str(age): metrics([r for r in predictions if r['age_months']==age]) for age in sorted(set(range(1,25))|{r['age_months'] for r in predictions})},
                predictions=predictions, checkpoint_sha256=checkpoint_hash,
                manifest_sha256=manifest_hash,
                provenance_sha256=hashlib.sha256(args.provenance.read_bytes()).hexdigest(),
                age_groups={f'{low}-{low+5}':metrics([r for r in predictions if low<=r['age_months']<low+6]) for low in (1,7,13,19)})
            if hashlib.sha256(selected_path.read_bytes()).hexdigest()!=checkpoint_hash:raise RuntimeError('Checkpoint changed during evaluation')
            if hashlib.sha256(args.manifest.read_bytes()).hexdigest()!=manifest_hash:raise RuntimeError('Manifest changed during evaluation')
            bird_errors=[sum(abs(r['prediction_months']-r['age_months']) for r in predictions if r['chicken_id']==bird)/count for bird,count in Counter(r['chicken_id'] for r in predictions).items()]
            rng=random.Random(2026)
            draws=sorted(sum(rng.choices(bird_errors,k=len(bird_errors)))/len(bird_errors) for _ in range(2000))
            report['bird_bootstrap_mae_interval_95_months']=[draws[49],draws[1949]]
            report['small_sample_warning']=len(bird_errors)<30
            with (args.output/'predictions.csv').open('w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=list(predictions[0]));writer.writeheader();writer.writerows(predictions)
            with (args.output/'confusion_rounded_months.csv').open('w',newline='',encoding='utf-8') as f:
                writer=csv.writer(f);writer.writerow(['actual_age/predicted_age',*range(1,25)])
                for age in range(1,25):writer.writerow([age,*[sum(round(r['age_months'])==age and max(1,min(24,round(r['prediction_months'])))==guess for r in predictions) for guess in range(1,25)]])
    (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('predictions','checkpoint')}, indent=2))
    return 0 if report['independent_evaluation_executed'] else 2


if __name__ == '__main__': sys.exit(main())
