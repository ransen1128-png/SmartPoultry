"""Lightweight deployment diagnostics; never loads a neural-network model."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def memory_limit_mb():
    limits=[]
    for name in ('/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory/memory.limit_in_bytes'):
        try:
            value=int(Path(name).read_text().strip())
            if 0<value<2**60:limits.append(value/1024**2)
        except (OSError,ValueError):pass
    return min(limits) if limits else None


def memory_warning():
    from core.free_inference import enabled
    if enabled():return ''
    limit=memory_limit_mb()
    if limit is not None and limit<1536:
        return 'Full chicken, leg and spur analysis requires a larger server instance (at least 2 GB RAM recommended). This server is limited to '+str(round(limit))+' MB. Age-only estimation remains separate.'
    return ''


def deployment_status():
    from core import free_inference
    return {
        'inference_runtime':'onnx' if free_inference.enabled() else 'pytorch',
        'onnx_models_present':all(free_inference.model_files_present(task) for task in ('age','chicken','detect','segment')),
        'chicken_weights_present':free_inference.model_files_present('chicken') if free_inference.enabled() else (ROOT/'ml_models/chicken_owlvit/model.safetensors').is_file(),
        'anatomy_weights_present':all(free_inference.model_files_present(task) for task in ('detect','segment')) if free_inference.enabled() else all((ROOT/'ml_models/poultry_vision'/name).is_file() for name in ('detect_45433d0396de91a7.pt','segment_e2e91c19fb1839e9.pt')),
        'detector_packages_present':importlib.util.find_spec('onnxruntime') is not None if free_inference.enabled() else all(importlib.util.find_spec(name) is not None for name in ('transformers','ultralytics')),
        'memory_limit_mb':memory_limit_mb(),
        'memory_warning':memory_warning(),
    }
