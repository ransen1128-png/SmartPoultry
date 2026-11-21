"""Expenses browser test CASE-112."""

from playwright.sync_api import expect

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase112(ExpensesBrowserCase):
    def test_case_112_one_egg_return_adds_eight_to_expenses(self):
        self.open_expenses()
        self.assert_total(0)
        self.fill_egg_return()
        record = self.save_expense('Save Return')
        self.assertEqual((record.expense_type, record.return_quantity, record.amount), ('return_eggs', 1, 8))
        section = self.page.locator('#returnedItemsSection')
        expect(section.get_by_role('heading', name='Returned Items / Eggs')).to_be_visible()
        row = section.locator('tbody tr').filter(has_text=self.return_reason)
        for value in ('Return Eggs', '1 pcs', '\u20b18.00'):
            expect(row.get_by_role('cell', name=value, exact=True)).to_be_visible()
        self.assert_total(8)
