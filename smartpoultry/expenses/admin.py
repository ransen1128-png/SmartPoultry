from django.contrib import admin
from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_type', 'description', 'return_quantity','return_unit','amount', 'date', 'category')
    list_filter = ('expense_type', 'category', 'date')
    search_fields = ('description', 'category')
