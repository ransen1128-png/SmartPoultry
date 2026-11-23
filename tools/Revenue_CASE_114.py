"""Revenue browser test CASE-114."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["114", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.revenue_browser import RevenueBrowserCase


class RevenueCase114(RevenueBrowserCase):
    def test_case_114_receipt_displays_both_items_and_order_total(self):
        first, second = self.save_two_item_order()
        notification = self.page.locator('#appDialog[open]')
        if notification.is_visible():
            notification.get_by_role('button', name='Close notification').click()
        expect(notification).to_be_hidden()
        self.revenue_row(first).get_by_role('link', name='View receipt').click()
        expect(self.page.get_by_role('heading', name='SMARTPOULTRY Sales Receipt')).to_be_visible()
        receipt = self.page.locator('main article')
        expect(receipt.get_by_text(f'Buyer: {self.buyer}', exact=True)).to_be_visible()
        expect(receipt.get_by_text('Total: \u20b1332.00', exact=True)).to_be_visible()
        rows = receipt.locator('tbody tr')
        expect(rows).to_have_count(2)
        for sale, product in ((first, 'Eggs (Medium)'), (second, 'Meat')):
            row = rows.filter(has=self.page.get_by_role('cell', name=sale.transaction_number, exact=True))
            expect(row.get_by_role('cell', name=product, exact=True)).to_be_visible()
