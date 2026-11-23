"""Revenue browser test CASE-107."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["107", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.revenue_browser import RevenueBrowserCase


class RevenueCase107(RevenueBrowserCase):
    def test_case_107_cannot_sell_more_than_fourteen_eggs(self):
        self.open_order()
        self.fill_order_header()
        line = self.fill_line(0, self.eggs, '15', '8')
        quantity = line.locator('[name="quantity"]')
        expect(quantity).to_have_attribute('max', '14')
        expect(line.locator('.production-available')).to_have_text('Available for this item: 14')
        self.submit()
        self.assert_sale_blocked(quantity, 'rangeOverflow')
