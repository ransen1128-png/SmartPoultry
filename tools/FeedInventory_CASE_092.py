"""Feed & Inventory browser test CASE-092."""

from playwright.sync_api import expect

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase092(FeedInventoryBrowserCase):
    def test_case_092_distribute_two_sacks(self):
        item = self.stock_fixture()
        self.open_inventory()
        self.fill_distribution()
        with self.page.expect_response(
            lambda response: response.url.endswith('/api/inventory/distributions/')
            and response.request.method == 'POST',
        ) as distribution:
            self.page.locator('#saveDistributionBtn').click()
        self.assertEqual(distribution.value.status, 201, distribution.value.text())
        lot = item.distributions.get()
        self.assertEqual((lot.branch_id, lot.quantity), (self.branch.pk, 2))
        self.page.reload(wait_until='domcontentloaded')
        self.assert_stock(item, 3)
        cells = self.branch_row(lot).get_by_role('cell')
        expect(cells.nth(0)).to_have_text(self.branch.name)
        expect(cells.nth(2)).to_contain_text('2 sacks')
