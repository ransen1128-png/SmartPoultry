"""Expenses browser test CASE-125."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["125", *sys.argv[1:]]))

from tools.automation_browser import expect


from expenses.models import Expense
from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase125(ExpensesBrowserCase):
    def test_case_125_cancel_utilities_expense_deletion(self):
        expense = Expense.objects.create(
            user=self.user, branch=self.branch, expense_type='utilities',
            description=self.utilities_description, amount=350, date=self.today,
        )
        self.open_expenses()
        row = self.expense_row(self.utilities_description)
        row.get_by_role('button', name='Delete', exact=True).click()
        confirmation = self.page.locator('#appConfirmDialog')
        expect(confirmation.get_by_text(
            f'Are you sure you want to delete this record? {self.utilities_description}', exact=True,
        )).to_be_visible()
        confirmation.get_by_role('button', name='Cancel', exact=True).click()
        expect(confirmation).to_be_hidden()
        expect(row).to_be_visible()
        self.page.reload(wait_until='domcontentloaded')
        expect(row).to_be_visible()
        expense.refresh_from_db()
        self.assertEqual(expense.amount, 350)
        self.assert_total(350)
