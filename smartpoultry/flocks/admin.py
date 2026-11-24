from django.contrib import admin
from .models import Flock


@admin.register(Flock)
class FlockAdmin(admin.ModelAdmin):
    list_display = ('flock_id', 'branch', 'user', 'breed', 'quantity', 'status', 'date_added')
    list_filter = ('status', 'breed', 'date_added')
    search_fields = ('flock_id', 'breed')
