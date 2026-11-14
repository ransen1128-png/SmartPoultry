from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from notifications.utils import create_activity_notification
from .models import Expense
from .serializers import ExpenseSerializer


class ExpenseViewSet(viewsets.ModelViewSet):
    """ViewSet for managing expenses."""
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user).select_related('branch','inventory_distribution__inventory')

    def perform_destroy(self, instance):
        if instance.inventory_purchase_id or instance.inventory_distribution_id or instance.flock_purchase_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('This expense is managed through its inventory distribution or flock purchase and cannot be deleted separately.')
        instance.delete()

    def perform_create(self, serializer):
        expense = serializer.save(user=self.request.user)
        create_activity_notification(
            self.request.user,
            f"Successfully added {expense.get_expense_type_display().lower()} expense",
            f"Recorded expense of PHP {expense.amount} for {expense.description}.",
            expense,
        )
