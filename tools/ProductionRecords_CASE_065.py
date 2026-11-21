"""Production Records browser test CASE-065."""

from playwright.sync_api import expect
from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase065(ProductionRecordsBrowserCase):
    def test_case_065_harvest_exceeds_live_count(self):
        self.fill_record(self.broilers, quantity='26')
        self.submit()
        expect(self.page.locator('main form')).to_contain_text('Only 25 live chicken are available in this flock.')
        self.assertFalse(ProductionRecord.objects.exists())
        self.broilers.refresh_from_db()
        self.assertEqual(self.broilers.quantity, 25)
