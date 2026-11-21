"""Revenue browser test CASE-096."""

from playwright.sync_api import expect

from tools.revenue_browser import RevenueBrowserCase


class RevenueCase096(RevenueBrowserCase):
    def test_case_096_cannot_sell_more_than_fourteen_eggs(self):
        self.open_order()
        self.fill_order_header()
        line = self.fill_line(0, self.eggs, '15', '8')
        quantity = line.locator('[name="quantity"]')
        expect(quantity).to_have_attribute('max', '14')
        expect(line.locator('.production-available')).to_have_text('Available for this item: 14')
        self.submit()
        self.assert_sale_blocked(quantity, 'rangeOverflow', 'Value must be less than or equal to 14.')
