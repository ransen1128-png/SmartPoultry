"""Production Records browser test CASE-062."""

from playwright.sync_api import expect
from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase062(ProductionRecordsBrowserCase):
    def test_case_062_missing_egg_size(self):
        self.fill_record(self.layers, egg_size='')
        self.submit()
        self.assert_required('#id_egg_size')
        expect(self.page.locator('#appDialogText')).to_have_text('Please select an item in the list.')
        self.assertFalse(ProductionRecord.objects.exists())
