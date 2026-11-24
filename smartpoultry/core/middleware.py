import json
from .audit import audit_context
from django.utils.cache import add_never_cache_headers


class PrivatePageCacheMiddleware:
    """Do not keep account pages or session-dependent API responses in caches."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        add_never_cache_headers(response)
        return response


class FarmActivityMiddleware:
    def __init__(self,get_response):self.get_response=get_response

    def __call__(self,request):
        actor=request.user if request.user.is_authenticated else None
        reason=''
        business_path=request.path.startswith(('/api/inventory/','/api/flocks/','/api/revenue/','/api/expenses/','/api/production/','/production-records/','/mortality-records/','/health-records/','/farm/','/change-history/'))
        if actor and business_path and request.method in ('POST','PUT','PATCH','DELETE'):
            try:
                data=json.loads(request.body) if request.content_type=='application/json' else request.POST
                if isinstance(data,dict):reason=str(data.get('correction_reason') or data.get('reason') or '')[:500]
            except (ValueError,UnicodeError):pass
        token=audit_context.set((actor,reason))
        try:
            if actor and request.method=='GET' and (request.path in ('/dashboard/','/flocks/','/notifications/') or request.path.startswith('/api/notifications/')):
                from notifications.readiness import notify_ready_flocks
                notify_ready_flocks(actor)
            if actor and business_path and request.method in ('POST','PUT','PATCH','DELETE'):
                from django.db import transaction
                with transaction.atomic():
                    response=self.get_response(request)
                    if response.status_code>=400:transaction.set_rollback(True)
                    return response
            return self.get_response(request)
        finally:audit_context.reset(token)
