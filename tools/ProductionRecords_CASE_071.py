"""Production Records browser test CASE-071."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["71", *sys.argv[1:]]))

from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase071(ProductionRecordsBrowserCase):
    def test_case_071_blank_quantity(self):
        self.fill_record(self.layers, quantity='')
        self.submit()
        self.assert_required('#id_quantity')
        self.assertFalse(ProductionRecord.objects.exists())
