from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class Notification(models.Model):
    """System notifications for users."""
    NOTIFICATION_TYPES = [
        ('alert', 'Alert'),
        ('warning', 'Warning'),
        ('info', 'Information'),
        ('success', 'Success'),
        ('error', 'Error'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, default='info')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    deduplication_key = models.CharField(max_length=160, null=True, blank=True, editable=False)
    
    def __str__(self):
        return f"{self.user} - {self.title}"
    
    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user','deduplication_key'],name='unique_owner_notification_key')]
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read', 'user']),
        ]


class Alert(models.Model):
    """Automated alerts for farm conditions."""
    ALERT_TYPES = [
        ('mortality', 'High Mortality'),
        ('low_inventory', 'Low Inventory'),
        ('production_drop', 'Production Drop'),
        ('health_issue', 'Health Issue'),
        ('expense_surge', 'Expense Surge'),
        ('revenue_drop', 'Revenue Drop'),
    ]
    
    ALERT_STATUS = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]
    
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    status = models.CharField(max_length=20, choices=ALERT_STATUS, default='active')
    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.IntegerField(choices=[(1, 'Low'), (2, 'Medium'), (3, 'High'), (4, 'Critical')], default=2)
    threshold_value = models.DecimalField(max_digits=15, decimal_places=2)
    current_value = models.DecimalField(max_digits=15, decimal_places=2)
    farm = models.ForeignKey('core.Farm', on_delete=models.CASCADE, related_name='alerts', null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.alert_type} - {self.title}"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]


class NotificationPreference(models.Model):
    """User notification preferences."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preference')
    email_alerts = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    in_app_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=False)
    alert_types = models.ManyToManyField('self', blank=True, symmetrical=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
    
    class Meta:
        verbose_name_plural = "Notification Preferences"
