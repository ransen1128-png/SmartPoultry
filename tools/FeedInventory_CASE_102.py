"""Feed & Inventory browser test CASE-102."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["102", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase102(FeedInventoryBrowserCase):
    def test_case_102_discard_and_reopen_distribution(self):
        item = self.stock_fixture()
        self.open_inventory()
        self.fill_distribution()
        modal = self.page.locator('#distributionModal')
        modal.get_by_role('button', name='Close', exact=True).last.click()
        dialog = self.page.locator('#appConfirmDialog')
        expect(dialog.get_by_text('Discard unsaved changes?', exact=True)).to_be_visible()
        dialog.get_by_role('button', name='Confirm', exact=True).click()
        expect(dialog).to_be_hidden()
        expect(modal).to_be_hidden()

        self.open_distribution()
        expect(self.page.locator('#distributionQuantity')).to_have_value('')
        self.assertFalse(item.distributions.exists())
