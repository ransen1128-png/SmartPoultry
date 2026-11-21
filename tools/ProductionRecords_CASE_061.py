"""Production Records browser test CASE-061."""

from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase061(ProductionRecordsBrowserCase):
    def test_case_061_blank_date(self):
        self.fill_record(self.layers, record_date='')
        self.submit()
        self.assert_required('#id_date')
        self.assertFalse(ProductionRecord.objects.exists())
