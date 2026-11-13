"""Read a curated evaluation summary without loading ML libraries or images."""
import json
import hashlib
from pathlib import Path
from .age_model_registry import candidate_entry


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
