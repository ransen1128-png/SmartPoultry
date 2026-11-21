"""Expenses browser test CASE-106."""

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase106(ExpensesBrowserCase):
    def test_case_106_description_amount_and_date_required(self):
        for name in ('description', 'amount', 'date'):
            with self.subTest(field=name):
                self.open_expenses()
                self.fill_expense(blank=name)
                self.page.get_by_role('button', name='Save Expense', exact=True).click()
                self.assert_native_error(
                    f'#addExpenseForm [name="{name}"]', 'valueMissing', 'Please fill out this field.',
                )
                self.assert_no_expenses()
