"""Production Records browser test CASE-063."""

from playwright.sync_api import expect
from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase063(ProductionRecordsBrowserCase):
    def test_case_063_zero_quantity(self):
        self.fill_record(self.layers, quantity='0')
        self.submit()
        expect(self.page.locator('main form')).to_contain_text('Production quantity must be greater than zero.')
        self.assertFalse(ProductionRecord.objects.exists())
