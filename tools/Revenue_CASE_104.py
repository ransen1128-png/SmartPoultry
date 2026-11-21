"""Revenue browser test CASE-104."""

from playwright.sync_api import expect

from tools.revenue_browser import RevenueBrowserCase


class RevenueCase104(RevenueBrowserCase):
    def test_case_104_sales_reduce_available_production_stock(self):
        self.assertEqual((self.eggs.available_quantity, self.meat.available_quantity), (14, 5))
        self.save_two_item_order()
        self.page.goto(f'{self.live_server_url}/production-records/')
        for record, quantity in ((self.eggs, '10'), (self.meat, '3')):
            row = self.page.locator(f'#availableProductionTable tr[data-production-id="{record.pk}"]')
            expect(row.get_by_role('cell').nth(8)).to_have_text(quantity)
            record.refresh_from_db()
            self.assertEqual(record.available_quantity, int(quantity))
