"""Keep hosted image inference from blocking health checks or duplicating models.

Gunicorn reads this file automatically when started from smartpoultry/.
Explicit --config in render.yaml also makes the intended configuration visible.
"""
import os

workers=1
worker_class='gthread'
threads=2
timeout=180
graceful_timeout=180
preload_app=False
accesslog='-'
errorlog='-'
capture_output=True

# Set before importing numerical libraries. Keep native thread pools small on
# the hosted CPU; application-level inference also serializes model execution.
os.environ.setdefault('SMARTPOULTRY_ML_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ['SMARTPOULTRY_WORKER_PROFILE']='single-worker-age-v1'
