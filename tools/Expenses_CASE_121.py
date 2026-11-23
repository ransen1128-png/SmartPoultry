"""Expenses browser test CASE-121."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["121", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase121(ExpensesBrowserCase):
    def test_case_121_utilities_adds_350_to_expenses(self):
        self.open_expenses()
        self.assert_total(0)
        self.fill_expense()
        record = self.save_expense('Save Expense')
        self.assertEqual((record.branch_id, record.expense_type, record.amount),
                         (self.branch.pk, 'utilities', 350))
        row = self.expense_row(self.utilities_description)
        expect(row.get_by_role('cell', name=self.branch.name, exact=True)).to_be_visible()
        expect(row.get_by_role('cell', name='\u20b1350.00', exact=True)).to_be_visible()
        self.assert_total(350)
