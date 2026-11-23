"""Feed & Inventory browser test CASE-098."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["98", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase098(FeedInventoryBrowserCase):
    def test_case_098_distribution_requires_branch(self):
        item = self.stock_fixture()
        self.open_inventory()
        self.fill_distribution(select_branch=False)
        self.page.locator('#saveDistributionBtn').click()
        self.assert_native_error('#distributionBranch', 'valueMissing')
        expect(self.page.locator('#distributionModal')).to_be_visible()
        self.assertFalse(item.distributions.exists())
        self.assert_stock(item, 5)
