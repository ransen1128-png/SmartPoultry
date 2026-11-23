"""Feed & Inventory browser test CASE-105."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["105", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase105(FeedInventoryBrowserCase):
    def test_case_105_history_shows_distribution_and_assigned_cost(self):
        lot = self.distribution_fixture()
        self.open_inventory()
        self.page.locator('#allDistributionHistoryBtn').click()
        modal = self.page.locator('#distributionModal')
        expect(modal.get_by_role('heading', name='Distribution history', exact=True)).to_be_visible()
        row = modal.locator('#distributionHistoryBody tr').filter(
            has=self.page.get_by_role('cell', name=self.item_name, exact=True),
        )
        expect(row).to_have_count(1)
        cells = row.get_by_role('cell')
        expect(cells.nth(2)).to_have_text(self.branch.name)
        expect(cells.nth(4)).to_contain_text('2 sacks')
        expect(cells.nth(6)).to_have_text('\u20b12000.00')
        self.assertEqual(lot.cost_snapshot, 2000)
