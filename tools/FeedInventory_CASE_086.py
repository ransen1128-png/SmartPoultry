"""Feed & Inventory browser test CASE-086."""

from playwright.sync_api import expect
from inventory.models import Inventory

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedInventoryCase086(FeedInventoryBrowserCase):
    def test_case_086_negative_stock_quantity(self):
        self.fill_item(quantity='-1')
        self.page.get_by_role('button', name='Save Item', exact=True).click()
        self.assert_native_error(
            '#addInventoryForm [name="quantity"]', 'rangeUnderflow',
            'Value must be greater than or equal to 0.',
        )
        expect(self.page.locator('#addInventoryModal')).to_be_visible()
        self.assertFalse(Inventory.objects.filter(user=self.user).exists())
