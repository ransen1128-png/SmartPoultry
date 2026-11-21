"""Production Records browser test CASE-064."""

from datetime import timedelta
from playwright.sync_api import expect
from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase064(ProductionRecordsBrowserCase):
    def test_case_064_early_broiler_harvest(self):
        earliest = self.broilers.ready_from
        self.fill_record(self.broilers, record_date=(earliest - timedelta(days=1)).isoformat())
        expect(self.page.locator('#broilerReadiness')).to_contain_text(earliest.isoformat())
        self.submit()
        self.assertTrue(self.page.locator('#id_date').evaluate('input => input.validity.rangeUnderflow'))
        expect(self.page.locator('#appDialog[open]')).to_be_visible()
        self.assertFalse(ProductionRecord.objects.exists())
