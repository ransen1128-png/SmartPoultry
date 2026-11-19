"""Owner-scoped replay protection for explicit financial operation keys."""
import hashlib
import json
from functools import wraps
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import MutationReceipt


def idempotent(operation):
    @wraps(operation)
    def wrapped(self, request, *args, **kwargs):
        key=request.headers.get('Idempotency-Key')
        if not key:
            return operation(self,request,*args,**kwargs)
        if len(key)>100 or not key.isascii() or not all(c.isalnum() or c in '-_' for c in key):
            raise ValidationError({'detail':'Invalid operation key.'})
        scope=request.path
        digest=hashlib.sha256(json.dumps(request.data,sort_keys=True,cls=DjangoJSONEncoder).encode()).hexdigest()
        with transaction.atomic():
            # One owner's simultaneous financial retries serialize across workers.
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            previous=MutationReceipt.objects.filter(user=request.user,scope=scope,key=key).first()
            if previous:
                if previous.request_hash!=digest:
                    return Response({'detail':'This operation key was already used for different data. Start a new entry.'},status=409)
                return Response(previous.response,status=previous.status,headers={'Idempotency-Replayed':'true'})
            response=operation(self,request,*args,**kwargs)
            if 200<=response.status_code<300:
                MutationReceipt.objects.create(user=request.user,scope=scope,key=key,request_hash=digest,
                    response=json.loads(json.dumps(response.data,cls=DjangoJSONEncoder)),status=response.status_code)
            return response
    return wrapped


class IdempotentCreateMixin:
    @idempotent
    def create(self,request,*args,**kwargs):
        return super().create(request,*args,**kwargs)
