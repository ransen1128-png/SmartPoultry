"""Revenue browser test CASE-112."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["112", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.revenue_browser import RevenueBrowserCase


class RevenueCase112(RevenueBrowserCase):
    def test_case_112_two_sales_increase_total_revenue_by_332(self):
        expect(self.page.locator('#totalRevenue')).to_have_text('\u20b10.00')
        eggs, meat = self.save_two_item_order()
        self.assertEqual((eggs.production_id, eggs.quantity, eggs.price_per_unit), (self.eggs.pk, 4, 8))
        self.assertEqual((meat.production_id, meat.quantity, meat.price_per_unit), (self.meat.pk, 2, 150))
        for sale, amount in ((eggs, '32.00'), (meat, '300.00')):
            row = self.revenue_row(sale)
            expect(row).to_be_visible()
            expect(row.get_by_role('cell').nth(8)).to_have_text(f'\u20b1{amount}')
        expect(self.page.locator('#totalRevenue')).to_have_text('\u20b1332.00')
