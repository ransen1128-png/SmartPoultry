"""Production Records browser test CASE-072."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["72", *sys.argv[1:]]))

from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase072(ProductionRecordsBrowserCase):
    def test_case_072_blank_date(self):
        self.fill_record(self.layers, record_date='')
        self.submit()
        self.assert_required('#id_date')
        self.assertFalse(ProductionRecord.objects.exists())
