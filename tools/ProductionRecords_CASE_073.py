"""Production Records browser test CASE-073."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["73", *sys.argv[1:]]))

from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase073(ProductionRecordsBrowserCase):
    def test_case_073_missing_egg_size(self):
        self.fill_record(self.layers, egg_size='')
        self.submit()
        self.assert_required('#id_egg_size')
        self.assertFalse(ProductionRecord.objects.exists())
