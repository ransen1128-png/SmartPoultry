"""Production Records browser test CASE-060."""

from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase060(ProductionRecordsBrowserCase):
    def test_case_060_blank_quantity(self):
        self.fill_record(self.layers, quantity='')
        self.submit()
        self.assert_required('#id_quantity')
        self.assertFalse(ProductionRecord.objects.exists())
