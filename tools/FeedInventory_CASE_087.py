"""Feed & Inventory browser test CASE-087."""

from playwright.sync_api import expect

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase087(FeedInventoryBrowserCase):
    def test_case_087_distribution_requires_branch(self):
        item = self.stock_fixture()
        self.open_inventory()
        self.fill_distribution(select_branch=False)
        self.page.locator('#saveDistributionBtn').click()
        self.assert_native_error('#distributionBranch', 'valueMissing', 'Please select an item in the list.')
        expect(self.page.locator('#distributionModal')).to_be_visible()
        self.assertFalse(item.distributions.exists())
        self.assert_stock(item, 5)
