"""Feed & Inventory browser test CASE-089."""

from playwright.sync_api import expect

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase089(FeedInventoryBrowserCase):
    def test_case_089_usage_cannot_exceed_two_sacks(self):
        lot = self.distribution_fixture()
        self.open_branch_usage(lot, '3')
        expect(self.page.locator('#branchUsageLabel')).to_contain_text('2 sacks available')
        self.page.locator('#branchUsageSave').click()
        self.assert_native_error(
            '#branchUsageQuantity', 'rangeOverflow', 'Value must be less than or equal to 2.',
        )
        expect(self.page.locator('#branchUsageModal')).to_be_visible()
        self.assertFalse(lot.usages.exists())
        expect(self.branch_row(lot).get_by_role('cell').nth(4)).to_contain_text('2 sacks')
