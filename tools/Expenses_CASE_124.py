"""Expenses browser test CASE-124."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["124", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase124(ExpensesBrowserCase):
    def test_case_124_egg_return_does_not_restore_production_stock(self):
        record = self.sold_egg_fixture()
        self.open_expenses()
        self.fill_egg_return()
        self.save_expense('Save Return')
        self.page.goto(f'{self.live_server_url}/production-records/')
        row = self.page.locator(f'#availableProductionTable tr[data-production-id="{record.pk}"]')
        expect(row.get_by_role('cell').nth(8)).to_have_text('10')
        record.refresh_from_db()
        self.assertEqual(record.available_quantity, 10)
