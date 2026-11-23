"""Expenses browser test CASE-117."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["117", *sys.argv[1:]]))

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase117(ExpensesBrowserCase):
    def test_case_117_description_amount_and_date_required(self):
        for name in ('description', 'amount', 'date'):
            with self.subTest(field=name):
                self.open_expenses()
                self.fill_expense(blank=name)
                self.page.get_by_role('button', name='Save Expense', exact=True).click()
                self.assert_native_error(
                    f'#addExpenseForm [name="{name}"]', 'valueMissing',
                )
                self.assert_no_expenses()
