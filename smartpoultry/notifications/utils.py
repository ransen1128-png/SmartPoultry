from notifications.models import Notification, NotificationPreference


def create_activity_notification(user, title, message, related_object=None, notification_type='success'):
    if not user or not user.is_authenticated:
        return None
    if NotificationPreference.objects.filter(user=user, in_app_notifications=False).exists():
        return None

    related_object_type = ''
    related_object_id = None
    if related_object is not None:
        related_object_type = related_object.__class__.__name__
        related_object_id = getattr(related_object, 'pk', None)

    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )
