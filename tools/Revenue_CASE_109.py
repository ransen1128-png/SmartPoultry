"""Revenue browser test CASE-109."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["109", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.revenue_browser import RevenueBrowserCase


class RevenueCase109(RevenueBrowserCase):
    def test_case_109_negative_price_is_rejected(self):
        self.open_order()
        self.fill_order_header()
        line = self.fill_line(0, self.eggs, '4', '-1')
        price = line.locator('[name="price_per_unit"]')
        expect(price).to_have_attribute('min', '0')
        self.submit()
        self.assert_sale_blocked(price, 'rangeUnderflow')
