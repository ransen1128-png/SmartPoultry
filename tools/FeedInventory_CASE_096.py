"""Feed & Inventory browser test CASE-096."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["96", *sys.argv[1:]]))

from tools.automation_browser import expect

from inventory.models import Inventory

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase096(FeedInventoryBrowserCase):
    def test_case_096_empty_required_inventory_fields(self):
        self.open_add_item()
        self.page.get_by_role('button', name='Save Item', exact=True).click()
        self.assert_native_error('#addInventoryForm [name="name"]', 'valueMissing')
        expect(self.page.locator('#addInventoryModal')).to_be_visible()
        self.assertFalse(Inventory.objects.filter(user=self.user).exists())
