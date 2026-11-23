"""Feed & Inventory browser test CASE-099."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["99", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase099(FeedInventoryBrowserCase):
    def test_case_099_distribution_cannot_exceed_five_sacks(self):
        item = self.stock_fixture()
        self.open_inventory()
        self.fill_distribution(quantity='6')
        self.page.locator('#saveDistributionBtn').click()
        expect(self.page.locator('#distributionFeedback')).to_contain_text('Only 5 sacks available.')
        expect(self.page.locator('#distributionModal')).to_be_visible()
        self.assertFalse(item.distributions.exists())
        self.assert_stock(item, 5)
