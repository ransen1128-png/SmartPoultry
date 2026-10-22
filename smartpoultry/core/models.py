from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType


class Farm(models.Model):
    """Main farm information model."""
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_farm')
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    established_date = models.DateField()
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Farms"


class Feedback(models.Model):
    """User feedback and reviews for the system."""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('archived', 'Archived'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_items')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    admin_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subject} ({self.get_status_display()})"

    class Meta:
        ordering = ['-created_at']


class RoosterAgeEstimate(models.Model):
    """Saved rooster age estimate based primarily on spur observations."""
    SPUR_VISIBILITY_CHOICES = [
        ('clear', 'Spurs clearly visible'),
        ('partial', 'Partially visible'),
        ('hidden', 'Hidden or not visible'),
        ('unassessed', 'Not assessed'),
    ]
    SPUR_LENGTH_CHOICES = [
        ('none', 'None visible'),
        ('buds', 'Small buds'),
        ('short', 'Short'),
        ('medium', 'Medium'),
        ('long', 'Long'),
        ('unassessed', 'Not assessed'),
    ]
    SPUR_THICKNESS_CHOICES = [
        ('thin', 'Thin'),
        ('moderate', 'Moderate'),
        ('thick', 'Thick'),
        ('unassessed', 'Not assessed'),
    ]
    POINT_SHAPE_CHOICES = [
        ('rounded', 'Rounded or blunt'),
        ('pointed', 'Sharp pointed'),
        ('worn', 'Worn or irregular'),
        ('unassessed', 'Not assessed'),
    ]
    CURVATURE_CHOICES = [
        ('straight', 'Straight'),
        ('slight', 'Slightly curved'),
        ('curved', 'Strongly curved'),
        ('unassessed', 'Not assessed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rooster_age_estimates')
    photo = models.FileField(upload_to='rooster_age_estimates/%Y/%m/', blank=True)
    photo_name = models.CharField(max_length=255, blank=True)
    chicken_detected = models.CharField(
        max_length=20,
        choices=[('yes', 'Yes'), ('no', 'No'), ('unassessed', 'Unable to determine')],
        default='unassessed',
    )
    spur_visibility = models.CharField(max_length=20, choices=SPUR_VISIBILITY_CHOICES, default='unassessed')
    spur_length = models.CharField(max_length=20, choices=SPUR_LENGTH_CHOICES, default='unassessed')
    spur_thickness = models.CharField(max_length=20, choices=SPUR_THICKNESS_CHOICES, default='unassessed')
    spur_point_shape = models.CharField(max_length=20, choices=POINT_SHAPE_CHOICES, default='unassessed')
    spur_curvature = models.CharField(max_length=20, choices=CURVATURE_CHOICES, default='unassessed')
    secondary_clues = models.TextField(blank=True)
    estimated_age_range = models.CharField(max_length=120)
    spur_observations = models.TextField()
    reasoning = models.TextField()
    confidence = models.CharField(max_length=40)
    limitations = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rooster estimate for {self.user} - {self.estimated_age_range}"

    class Meta:
        ordering = ['-created_at']


class TransactionRecord(models.Model):
    """Immutable ledger entry for financial transactions."""
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    ACTION_TYPES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
    ]

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.CharField(max_length=255)
    transaction_date = models.DateField()
    source_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    source_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_label = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.amount} - {self.description}"

    class Meta:
        ordering = ['-created_at']


class Branch(models.Model):
    """Represents a branch/location under a Farm."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    contact_number = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.farm})"

    class Meta:
        verbose_name_plural = "Branches"
        ordering = ['name']
