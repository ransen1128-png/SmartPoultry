"""Revenue browser test CASE-108."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["108", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.revenue_browser import RevenueBrowserCase


class RevenueCase108(RevenueBrowserCase):
    def test_case_108_sale_quantity_below_minimum(self):
        self.open_order()
        self.fill_order_header()
        line = self.fill_line(0, self.eggs, '0', '8')
        quantity = line.locator('[name="quantity"]')
        expect(quantity).to_have_attribute('min', '0.01')
        self.submit()
        self.assert_sale_blocked(quantity, 'rangeUnderflow')
