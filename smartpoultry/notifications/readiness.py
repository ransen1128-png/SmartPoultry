from django.utils import timezone
from flocks.models import Flock
from .models import Notification, NotificationPreference


def notify_ready_flocks(user=None):
    today=timezone.localdate()
    flocks=Flock.objects.filter(breed='broilers',status='active',quantity__gt=0,
        branch__status='active',placement_date__isnull=False).select_related('branch','user')
    if user:flocks=flocks.filter(user=user)
    count=0
    for flock in flocks:
        if flock.ready_from>today or not flock.user_id:continue
        if NotificationPreference.objects.filter(user_id=flock.user_id,in_app_notifications=False).exists():continue
        _,created=Notification.objects.get_or_create(user_id=flock.user_id,
            deduplication_key=f'broiler-ready:{flock.pk}:{flock.placement_date}',defaults={
                'notification_type':'info','title':f'Broilers ready: {flock.display_label}'[:255],
                'message':f'{flock.branch.name}: flock {flock.flock_id} is {(today-flock.placement_date).days} days after delivery / hatch. Production and sale are allowed from {flock.ready_from}; expected window ends {flock.readiness_window_end}.',
                'related_object_type':'Flock','related_object_id':flock.pk})
        count+=created
    return count
