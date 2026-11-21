"""Revenue browser test CASE-098."""

from playwright.sync_api import expect

from tools.revenue_browser import RevenueBrowserCase


class RevenueCase098(RevenueBrowserCase):
    def test_case_098_negative_price_is_rejected(self):
        self.open_order()
        self.fill_order_header()
        line = self.fill_line(0, self.eggs, '4', '-1')
        price = line.locator('[name="price_per_unit"]')
        expect(price).to_have_attribute('min', '0')
        self.submit()
        self.assert_sale_blocked(price, 'rangeUnderflow', 'Value must be greater than or equal to 0.')
