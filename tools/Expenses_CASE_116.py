"""Expenses browser test CASE-116."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["116", *sys.argv[1:]]))

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase116(ExpensesBrowserCase):
    def test_case_116_expense_requires_branch(self):
        self.open_expenses()
        self.fill_expense(blank='branch')
        self.page.get_by_role('button', name='Save Expense', exact=True).click()
        self.assert_native_error(
            '#addExpenseForm [name="branch"]', 'valueMissing',
        )
        self.assert_no_expenses()
