"""Feed & Inventory browser test CASE-085."""

from playwright.sync_api import expect
from inventory.models import Inventory

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase085(FeedInventoryBrowserCase):
    def test_case_085_empty_required_inventory_fields(self):
        self.open_add_item()
        self.page.get_by_role('button', name='Save Item', exact=True).click()
        self.assert_native_error('#addInventoryForm [name="name"]', 'valueMissing', 'Please fill out this field.')
        expect(self.page.locator('#addInventoryModal')).to_be_visible()
        self.assertFalse(Inventory.objects.filter(user=self.user).exists())
