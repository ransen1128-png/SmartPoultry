"""Feed & Inventory browser test CASE-097."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["97", *sys.argv[1:]]))

from playwright.sync_api import expect
from inventory.models import Inventory

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase097(FeedInventoryBrowserCase):
    def test_case_097_negative_stock_quantity(self):
        self.fill_item(quantity='-1')
        self.page.get_by_role('button', name='Save Item', exact=True).click()
        self.assert_native_error(
            '#addInventoryForm [name="quantity"]', 'rangeUnderflow',
        )
        expect(self.page.locator('#addInventoryModal')).to_be_visible()
        self.assertFalse(Inventory.objects.filter(user=self.user).exists())
