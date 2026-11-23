"""Revenue browser test CASE-113."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["113", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.revenue_browser import RevenueBrowserCase


class RevenueCase113(RevenueBrowserCase):
    def test_case_113_generated_order_and_transaction_numbers(self):
        first, second = self.save_two_item_order()
        self.assertRegex(first.order_number, r'^ORD-[A-F0-9]+$')
        self.assertEqual(first.order_number, second.order_number)
        self.assertNotEqual(first.transaction_number, second.transaction_number)
        for sale in (first, second):
            self.assertRegex(sale.transaction_number, r'^TXN-[A-F0-9]+$')
            cells = self.revenue_row(sale).get_by_role('cell')
            expect(cells.nth(4)).to_have_text(sale.order_number)
            expect(cells.nth(5)).to_have_text(sale.transaction_number)
