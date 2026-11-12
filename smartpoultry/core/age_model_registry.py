"""Small model registry, safe to inspect without importing an ML runtime."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / 'spur_age/models/age_candidates.json'


def candidate_entry():
    try:
        entry = json.loads(REGISTRY.read_text())['finetuned']
        path = (ROOT / entry['path']).resolve()
        path.relative_to((ROOT / 'spur_age/experiments').resolve())
        return {**entry, 'resolved_path': path} if path.is_file() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None
