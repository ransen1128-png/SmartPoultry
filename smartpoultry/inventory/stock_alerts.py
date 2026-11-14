"""One in-app warning per low-stock episode; never sends external messages."""
from .models import Inventory
from notifications.models import Notification,NotificationPreference


def stock_warning_message(item, distribution=None):
    if item.minimum_stock is None or item.quantity>item.minimum_stock:
        return None
    message=f'{item.name}: {item.quantity} {item.unit} remaining; minimum {item.minimum_stock} {item.unit}.'
    if item.package_size is not None:
        message+=f' Remaining contents: {item.total_content} {item.content_unit}.'
    if distribution is not None:
        message+=f' After distributing {distribution.quantity} {item.unit} to {distribution.branch.name}.'
    return message


def refresh_stock_alert(item, distribution=None):
    low=item.minimum_stock is not None and item.quantity<=item.minimum_stock
    if not low:
        Inventory.objects.filter(pk=item.pk,low_stock_alerted=True).update(low_stock_alerted=False)
        item.low_stock_alerted=False
        return
    if not item.user_id or NotificationPreference.objects.filter(user_id=item.user_id,in_app_notifications=False).exists():
        return
    changed=Inventory.objects.filter(pk=item.pk,low_stock_alerted=False).update(low_stock_alerted=True)
    if changed:
        Notification.objects.create(user_id=item.user_id,notification_type='warning',
            title=f'Low stock: {item.name}'[:255],message=stock_warning_message(item,distribution),
            related_object_type='Inventory',related_object_id=item.pk)
    item.low_stock_alerted=True
