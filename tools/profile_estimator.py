"""Time real local model startup and inference without creating database records."""
import importlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
results = {}


def timed(name, operation):
    start = time.perf_counter()
    result = operation()
    results[name] = round(time.perf_counter() - start, 3)
    print(name, results[name], 'seconds', flush=True)
    return result


age = timed('age_runtime_import', lambda: importlib.import_module('core.rooster_age_classifier'))
chicken = importlib.import_module('core.chicken_detection')
anatomy = importlib.import_module('core.poultry_vision')
assert timed('age_model_load', age.model_is_ready)
assert timed('chicken_model_load', chicken.load_detector) is not None
assert timed('anatomy_models_load', anatomy.vision_is_ready)
import torch
results['initial_torch_threads'] = torch.get_num_threads()
with (ROOT / 'spurs images/4months.jpg').open('rb') as image:
    for prefix, count in [('initial', None), ('four_threads', 4)]:
        if count:
            torch.set_num_threads(count)
        image.seek(0)
        assert timed(prefix + '_age_prediction', lambda: age.predict_rooster_age(image)) is not None
        image.seek(0)
        assert timed(prefix + '_chicken_detection', lambda: chicken.detect_chicken(image))['status'] != 'error'
        image.seek(0)
        assert timed(prefix + '_anatomy_analysis', lambda: anatomy.analyze_poultry(image))['status'] == 'completed'
    results['final_torch_threads'] = torch.get_num_threads()
out = ROOT / 'reports/performance'
out.mkdir(parents=True, exist_ok=True)
(out / 'estimator_profile.json').write_text(json.dumps(results, indent=2))
