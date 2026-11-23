"""Feed & Inventory browser test CASE-100."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["100", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase100(FeedInventoryBrowserCase):
    def test_case_100_usage_cannot_exceed_two_sacks(self):
        lot = self.distribution_fixture()
        self.open_branch_usage(lot, '3')
        expect(self.page.locator('#branchUsageLabel')).to_contain_text('2 sacks available')
        self.page.locator('#branchUsageSave').click()
        self.assert_native_error(
            '#branchUsageQuantity', 'rangeOverflow',
        )
        expect(self.page.locator('#branchUsageModal')).to_be_visible()
        self.assertFalse(lot.usages.exists())
        expect(self.branch_row(lot).get_by_role('cell').nth(4)).to_contain_text('2 sacks')
