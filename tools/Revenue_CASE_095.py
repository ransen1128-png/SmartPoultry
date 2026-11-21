"""Revenue browser test CASE-095."""

from tools.revenue_browser import RevenueBrowserCase


class RevenueCase095(RevenueBrowserCase):
    def test_case_095_required_fields_block_sale(self):
        self.open_order()
        self.submit()
        self.assert_sale_blocked(
            self.modal.get_by_label('Buyer Name', exact=True),
            'valueMissing', 'Please fill out this field.',
        )
