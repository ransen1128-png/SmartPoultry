"""Capture business-field changes only; exclude passwords, API keys and photos."""
from contextvars import ContextVar
from django.db.models.signals import pre_save, post_save, pre_delete
from .models import AuditEvent

audit_context=ContextVar('farm_audit_context',default=(None,''))
FIELDS={
    'inventory.Inventory':['name','item_type','quantity','unit','cost_per_unit','minimum_stock','package_size','content_unit'],
    'inventory.InventoryDistribution':['inventory_id','branch_id','quantity','date','reversed_at','reversal_reason'],
    'inventory.InventoryUsage':['distribution_id','quantity','date','reason','voided_at','void_reason'],
    'flocks.Flock':['branch_id','flock_id','breed','quantity','status','placement_date','acquisition_source','purchase_amount','delivery_cost'],
    'production.ProductionRecord':['branch_id','flock_id','product_type','egg_size','quantity','unit','date'],
    'production.MortalityRecord':['branch_id','flock_id','quantity','date','reason','description'],
    'revenue.Revenue':['branch_id','production_id','quantity','price_per_unit','total_amount','date','order_number','transaction_number'],
    'expenses.Expense':['branch_id','expense_type','amount','date','description'],
    'core.Branch':['name','location','status'],
}


def snapshot(instance):
    return {field:str(getattr(instance,field)) if getattr(instance,field,None) is not None else None
            for field in FIELDS[instance._meta.label] if hasattr(instance,field)}


def record_explicit_change(instance,before,after,action):
    owner_id=getattr(instance,'user_id',None)
    if instance._meta.label=='core.Branch':owner_id=instance.farm.owner_id
    if not owner_id:return
    actor,reason=audit_context.get()
    AuditEvent.objects.create(owner_id=owner_id,actor=actor,actor_label=actor.username if actor else 'System',
        object_type=instance._meta.label,object_id=instance.pk,action=action,before=before,after=after,
        reason=reason or getattr(instance,'void_reason','') or getattr(instance,'reversal_reason',''))


def remember(sender,instance,raw=False,using='default',**kwargs):
    if raw:return
    previous=sender.objects.using(using).filter(pk=instance.pk).first() if instance.pk else None
    instance._audit_before=snapshot(previous) if previous else {}


def saved(sender,instance,created,raw=False,using='default',**kwargs):
    if raw:return
    before=getattr(instance,'_audit_before',{});after=snapshot(sender.objects.using(using).get(pk=instance.pk))
    if created or before!=after:record_explicit_change(instance,before,after,'created' if created else 'updated')


def deleted(sender,instance,origin=None,**kwargs):
    # Deleting an account also deletes its audit; do not recreate owner references.
    from django.contrib.auth import get_user_model
    if isinstance(origin,get_user_model()) or getattr(origin,'model',None)==get_user_model():return
    record_explicit_change(instance,snapshot(instance),{},'deleted')


def connect_audit():
    from django.apps import apps
    for label in FIELDS:
        model=apps.get_model(label)
        for signal,receiver in ((pre_save,remember),(post_save,saved),(pre_delete,deleted)):
            signal.connect(receiver,sender=model,weak=False,dispatch_uid='farm_audit_'+label+'_'+receiver.__name__)
