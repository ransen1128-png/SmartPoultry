"""Feed & Inventory browser test CASE-101."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["101", *sys.argv[1:]]))

from tools.automation_browser import expect

from inventory.models import Inventory

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase101(FeedInventoryBrowserCase):
    def test_case_101_add_five_sacks_of_feed(self):
        self.fill_item()
        with self.page.expect_response(
            lambda response: response.url.endswith('/api/inventory/items/')
            and response.request.method == 'POST',
        ) as creation:
            self.page.get_by_role('button', name='Save Item', exact=True).click()
        self.assertEqual(creation.value.status, 201, creation.value.text())
        expect(self.page.locator('#addInventoryModal')).to_be_hidden()
        row = self.inventory_row()
        expect(row.get_by_role('cell').nth(3)).to_have_text('5 sacks of 25 kg (125 kg total)')
        expect(row.get_by_role('cell').nth(5)).to_have_text('\u20b15000.00')
        item = Inventory.objects.get(user=self.user, name=self.item_name)
        self.assertEqual((item.quantity, item.total_content, item.total_value), (5, 125, 5000))
