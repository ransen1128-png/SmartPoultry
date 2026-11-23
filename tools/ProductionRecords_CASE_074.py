"""Production Records browser test CASE-074."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["74", *sys.argv[1:]]))

from tools.automation_browser import expect

from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase074(ProductionRecordsBrowserCase):
    def test_case_074_zero_quantity(self):
        self.fill_record(self.layers, quantity='0')
        self.submit()
        expect(self.page.locator('main form')).to_contain_text('Production quantity must be greater than zero.')
        self.assertFalse(ProductionRecord.objects.exists())
