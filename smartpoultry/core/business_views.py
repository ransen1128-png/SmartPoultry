from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render,get_object_or_404,redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import AuditEvent


@login_required
@never_cache
def sales_receipt(request,sale_id):
    from revenue.models import Revenue
    sale=get_object_or_404(Revenue,user=request.user,pk=sale_id)
    rows=list(Revenue.objects.filter(user=request.user,order_group=sale.order_group).select_related('production','branch').order_by('pk')) if sale.order_group else [sale]
    return render(request,'sales_receipt.html',{'sale':sale,'rows':rows,'total':sum((row.total_amount for row in rows),Decimal('0'))})


@login_required
@never_cache
@require_http_methods(['GET','POST'])
def activity_history(request):
    if request.method=='POST':
        event=get_object_or_404(AuditEvent,owner=request.user,pk=request.POST.get('event'))
        reason=request.POST.get('reason','').strip()
        if reason and len(reason)<=500:
            AuditEvent.objects.create(owner=request.user,actor=request.user,actor_label=request.user.username,
                object_type=event.object_type,object_id=event.object_id,action='note',
                after={'audit_event_id':event.pk},reason=reason)
            messages.success(request, 'Changes saved successfully.')
        else:
            messages.warning(request, 'Enter a note with at most 500 characters.')
        return redirect('activity_history')
    rows=AuditEvent.objects.filter(owner=request.user)
    kind=request.GET.get('type','')
    if kind:rows=rows.filter(object_type=kind)
    page=Paginator(rows,50).get_page(request.GET.get('page'))
    for event in page:
        keys=set(event.before)|set(event.after)
        event.changes=[{'field':key,'before':event.before.get(key),'after':event.after.get(key)} for key in sorted(keys) if event.before.get(key)!=event.after.get(key)]
    return render(request,'activity_history.html',{'page':page,'kind':kind,'kinds':AuditEvent.objects.filter(owner=request.user).values_list('object_type',flat=True).distinct().order_by('object_type')})
