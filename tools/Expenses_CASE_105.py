"""Expenses browser test CASE-105."""

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase105(ExpensesBrowserCase):
    def test_case_105_expense_requires_branch(self):
        self.open_expenses()
        self.fill_expense(blank='branch')
        self.page.get_by_role('button', name='Save Expense', exact=True).click()
        self.assert_native_error(
            '#addExpenseForm [name="branch"]', 'valueMissing', 'Please select an item in the list.',
        )
        self.assert_no_expenses()
