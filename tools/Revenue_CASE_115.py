"""Revenue browser test CASE-115."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["115", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.revenue_browser import RevenueBrowserCase


class RevenueCase115(RevenueBrowserCase):
    def test_case_115_sales_reduce_available_production_stock(self):
        self.assertEqual((self.eggs.available_quantity, self.meat.available_quantity), (14, 5))
        self.save_two_item_order()
        self.page.goto(f'{self.live_server_url}/production-records/')
        for record, quantity in ((self.eggs, '10'), (self.meat, '3')):
            row = self.page.locator(f'#availableProductionTable tr[data-production-id="{record.pk}"]')
            expect(row.get_by_role('cell').nth(8)).to_have_text(quantity)
            record.refresh_from_db()
            self.assertEqual(record.available_quantity, int(quantity))
