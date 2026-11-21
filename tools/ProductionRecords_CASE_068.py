"""Production Records browser test CASE-068."""

from playwright.sync_api import expect
from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase068(ProductionRecordsBrowserCase):
    def test_case_068_record_twelve_medium_eggs(self):
        self.fill_record(self.layers)
        self.submit()
        expect(self.page).to_have_url(self.records_url)
        record = ProductionRecord.objects.get(flock=self.layers)
        cells = self.record_row(record).get_by_role('cell')
        expect(cells.nth(5)).to_have_text('Medium')
        expect(cells.nth(6)).to_have_text('12')
        expect(cells.nth(8)).to_have_text('12')
