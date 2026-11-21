"""Feed & Inventory browser test CASE-088."""

from playwright.sync_api import expect

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase088(FeedInventoryBrowserCase):
    def test_case_088_distribution_cannot_exceed_five_sacks(self):
        item = self.stock_fixture()
        self.open_inventory()
        self.fill_distribution(quantity='6')
        self.page.locator('#saveDistributionBtn').click()
        expect(self.page.locator('#appDialog[open] #appDialogText')).to_contain_text('Only 5 sacks available.')
        expect(self.page.locator('#distributionModal')).to_be_visible()
        self.assertFalse(item.distributions.exists())
        self.assert_stock(item, 5)
