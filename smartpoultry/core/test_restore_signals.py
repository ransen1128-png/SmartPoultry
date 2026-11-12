from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from core.signals import record_revenue_save, record_expense_save, create_expense_for_inventory_create


class FixtureRestoreSignalTests(SimpleTestCase):
    def test_restoring_records_does_not_create_duplicate_transactions_or_expenses(self):
        with patch('core.signals._record_revenue_transaction') as revenue, \
             patch('core.signals._record_expense_transaction') as expense, \
             patch('core.signals.Expense.objects') as purchases:
            for handler in (record_revenue_save, record_expense_save, create_expense_for_inventory_create):
                handler(None, SimpleNamespace(), created=True, using='default', raw=True)
            revenue.assert_not_called()
            expense.assert_not_called()
            purchases.assert_not_called()
            purchases.using.assert_not_called()
