"""Expenses browser test CASE-110."""

from playwright.sync_api import expect

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase110(ExpensesBrowserCase):
    def test_case_110_utilities_adds_350_to_expenses(self):
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
