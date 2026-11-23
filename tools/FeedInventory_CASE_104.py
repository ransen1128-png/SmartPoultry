"""Feed & Inventory browser test CASE-104."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["104", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase104(FeedInventoryBrowserCase):
    def test_case_104_record_one_sack_used(self):
        lot = self.distribution_fixture()
        self.open_branch_usage(lot, '1')
        with self.page.expect_response(
            lambda response: response.url.endswith('/api/inventory/usage/')
            and response.request.method == 'POST',
        ) as usage:
            self.page.locator('#branchUsageSave').click()
        self.assertEqual(usage.value.status, 201, usage.value.text())
        expect(self.page.locator('#branchUsageModal')).to_be_hidden()
        cells = self.branch_row(lot).get_by_role('cell')
        expect(cells.nth(3)).to_contain_text('1 sacks')
        expect(cells.nth(4)).to_contain_text('1 sacks')
        self.assertEqual(lot.usages.get().quantity, 1)
