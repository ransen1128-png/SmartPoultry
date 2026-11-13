from django.db import models
from django.contrib.auth.models import AbstractUser, Group


class UserProfile(AbstractUser):
    """Extended user profile with farm information."""
    ROLE_CHOICES = [
        ('admin', 'Farm Administrator'),
        ('manager', 'Farm Manager'),
        ('staff', 'Staff Member'),
        ('viewer', 'Viewer Only'),
    ]
    
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    farm = models.ForeignKey('core.Farm', on_delete=models.SET_NULL, null=True, blank=True)
    is_active_user = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
    
    class Meta:
        verbose_name_plural = "User Profiles"


class UserRole(models.Model):
    """Custom user roles for permission management."""
    PERMISSIONS = [
        ('view_dashboard', 'View Dashboard'),
        ('manage_flocks', 'Manage Flocks'),
        ('manage_inventory', 'Manage Inventory'),
        ('manage_finance', 'Manage Finance'),
        ('view_reports', 'View Reports'),
        ('generate_reports', 'Generate Reports'),
        ('manage_users', 'Manage Users'),
        ('system_admin', 'System Administration'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    permissions = models.ManyToManyField('auth.Permission')
    is_custom = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "User Roles"
