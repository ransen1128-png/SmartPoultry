"""Select the inference runtime without importing PyTorch on a free host."""
from functools import wraps
import threading
from . import free_inference

_REQUEST_SLOT=threading.BoundedSemaphore(1)


def model_is_ready(model_variant='original'):
    if free_inference.enabled():return free_inference.age_ready(model_variant)
    from core.rooster_age_classifier import model_is_ready as ready
    return ready(model_variant)


def predict_rooster_age(source,model_variant='original'):
    if free_inference.enabled():return free_inference.predict_age(source,model_variant)
    from core.rooster_age_classifier import predict_rooster_age as predict
    return predict(source,model_variant)


def bound_estimator_requests(view):
    @wraps(view)
    def bounded(request,*args,**kwargs):
        if request.method!='POST' or not free_inference.enabled():return view(request,*args,**kwargs)
        if not _REQUEST_SLOT.acquire(blocking=False):
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.warning(request,'Another image is being analyzed. Please try again shortly.')
            return redirect('rooster_age_estimator')
        try:return view(request,*args,**kwargs)
        finally:_REQUEST_SLOT.release()
    return bounded
