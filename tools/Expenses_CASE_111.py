"""Expenses browser test CASE-111."""

from playwright.sync_api import expect

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase111(ExpensesBrowserCase):
    def test_case_111_inventory_distribution_does_not_double_count_purchase(self):
        lot = self.distribution_fixture()
        purchase = lot.inventory.purchase_expense
        allocation = lot.expense
        purchase.refresh_from_db()
        self.assertEqual((purchase.amount, allocation.amount), (3000, 2000))
        self.assertEqual(lot.quantity, 2)
        self.open_expenses()
        row = self.expense_row(allocation.description)
        expect(row.get_by_role('cell', name=self.branch.name, exact=True)).to_be_visible()
        expect(row.get_by_role('cell', name='\u20b12000.00', exact=True)).to_be_visible()
        expect(row.get_by_role('cell', name='Inventory distribution', exact=True)).to_be_visible()
        self.assert_total(5000)
