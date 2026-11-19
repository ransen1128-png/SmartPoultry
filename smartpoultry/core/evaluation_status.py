"""Read a curated evaluation summary without loading ML libraries or images."""
import json
import hashlib
from pathlib import Path
from .age_model_registry import candidate_entry


def tested_age_range(prediction):
    """Only show ranges tied to a provenance-screened, separately tested artifact."""
    unavailable='Tested age range unavailable: verified unseen-chicken calibration and testing are required.'
    if not prediction or not prediction.get('model_sha256'):return unavailable
    root=Path(__file__).resolve().parents[2]
    try:
        content=(root/'reports/unseen_evaluation/report.json').read_bytes()
        evaluation=json.loads(content)
        interval=json.loads((root/'reports/unseen_evaluation/intervals.json').read_text())
        if (interval.get('status')!='tested' or not evaluation.get('independent_evaluation_executed')
            or not evaluation.get('provenance_sha256') or interval.get('evaluation_sha256')!=hashlib.sha256(content).hexdigest()
            or interval.get('checkpoint_sha256')!=prediction['model_sha256']
            or evaluation.get('checkpoint_sha256')!=prediction['model_sha256']
            or interval.get('calibration_chickens',0)<20 or interval.get('test_chickens',0)<20):return unavailable
        import math
        radius=float(interval['radius_months']);age=float(prediction['age_months'])
        coverage=float(interval['held_out_bird_coverage'])
        if not math.isfinite(radius) or radius<0 or not math.isfinite(age) or not 1<=age<=24 or not 0<=coverage<=1:return unavailable
        # Round outwards so displayed endpoints never narrow the tested interval.
        low=math.floor(max(1,age-radius)*10)/10;high=math.ceil(min(24,age+radius)*10)/10
        return f'{low:.1f}–{high:.1f} months; observed coverage {coverage:.0%} on {interval["test_chickens"]} separate test chickens (90% target).'
    except (OSError,ValueError,KeyError,TypeError):return unavailable


def age_evaluation_status():
    root=Path(__file__).resolve().parents[2]
    try:
        report=json.loads((root/'reports/unseen_evaluation/report.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return 'No verified independent evaluation has been recorded.'
    if not report.get('independent_evaluation_executed'):
        return 'Independent testing needs age/identity records confirming that the photographed chickens were excluded from all prior training. Known-image duplicate screening has not established a qualifying test set.'
    entry=candidate_entry()
    active_hash=entry['sha256'] if entry else hashlib.sha256((root/'spur_age/models/spur_age_model.pth').read_bytes()).hexdigest()
    if report.get('checkpoint_sha256')!=active_hash:
        return 'The recorded evaluation applies to another model checkpoint; the current model needs evaluation.'
    return f"Evaluation recorded for {report.get('distinct_chickens',0)} registered chickens; MAE {report['metrics']['mae_months']:.2f} months. Identity and training-exclusion claims depend on the supplied human-verified register."
