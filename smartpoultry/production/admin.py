from django.contrib import admin
from .models import ProductionRecord, MortalityRecord, BreedInformation, HealthRecord


@admin.register(ProductionRecord)
class ProductionRecordAdmin(admin.ModelAdmin):
    list_display = ('flock', 'product_type', 'egg_size', 'quantity', 'unit', 'date')
    list_filter = ('product_type', 'egg_size', 'date', 'flock')
    search_fields = ('flock__flock_id', 'product_type')


@admin.register(MortalityRecord)
class MortalityRecordAdmin(admin.ModelAdmin):
    list_display = ('flock', 'quantity', 'reason', 'date')
    list_filter = ('reason', 'date', 'flock')
    search_fields = ('flock__flock_id',)


@admin.register(BreedInformation)
class BreedInformationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'egg_production_per_year', 'growth_period_days')
    list_filter = ('type',)
    search_fields = ('name', 'type')


@admin.register(HealthRecord)
class HealthRecordAdmin(admin.ModelAdmin):
    list_display = ('flock', 'health_status', 'disease_name', 'date')
    list_filter = ('health_status', 'date', 'flock')
    search_fields = ('flock__flock_id', 'disease_name')
