"""Bound CPU concurrency for the local image-analysis models."""
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def configure_cpu_runtime():
    import torch
    try:
        threads = int(os.environ.get('SMARTPOULTRY_ML_THREADS', '4'))
    except ValueError:
        threads = 4
    threads = max(1, min(threads, os.cpu_count() or 1))
    torch.set_num_threads(threads)
    return threads
