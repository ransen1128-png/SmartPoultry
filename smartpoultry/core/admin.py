from django.contrib import admin
from .models import Farm, Feedback, RoosterAgeEstimate, TransactionRecord, Branch


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'location', 'contact_email', 'created_at')
    search_fields = ('name', 'owner__username', 'location', 'contact_email')


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('subject', 'user', 'rating', 'status', 'created_at')
    list_filter = ('status', 'rating', 'created_at')
    search_fields = ('subject', 'message', 'user__username', 'user__email')


@admin.register(TransactionRecord)
class TransactionRecordAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_type',
        'action',
        'amount',
        'description',
        'transaction_date',
        'source_label',
        'created_at',
    )
    list_filter = ('transaction_type', 'action', 'transaction_date', 'created_at')
    search_fields = ('description', 'source_label', 'notes')
    readonly_fields = (
        'transaction_type',
        'action',
        'amount',
        'description',
        'transaction_date',
        'source_content_type',
        'source_object_id',
        'source_label',
        'notes',
        'metadata',
        'created_at',
    )


@admin.register(RoosterAgeEstimate)
class RoosterAgeEstimateAdmin(admin.ModelAdmin):
    list_display = ('user', 'estimated_age_range', 'confidence', 'spur_visibility', 'created_at')
    list_filter = ('spur_visibility', 'spur_length', 'spur_thickness', 'confidence', 'created_at')
    search_fields = ('user__username', 'user__email', 'photo_name', 'estimated_age_range', 'reasoning')
    readonly_fields = ('created_at',)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'farm', 'location', 'contact_number', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'farm__name', 'location', 'contact_number')
