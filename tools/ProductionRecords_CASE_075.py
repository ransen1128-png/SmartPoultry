"""Production Records browser test CASE-075."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["75", *sys.argv[1:]]))

from datetime import timedelta
from playwright.sync_api import expect
from production.models import ProductionRecord

from tools.automation_browser import expect_field_error
from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase075(ProductionRecordsBrowserCase):
    def test_case_075_early_broiler_harvest(self):
        earliest = self.broilers.ready_from
        self.fill_record(self.broilers, record_date=(earliest - timedelta(days=1)).isoformat())
        expect(self.page.locator('#broilerReadiness')).to_contain_text(earliest.isoformat())
        self.submit()
        self.assertTrue(self.page.locator('#id_date').evaluate('input => input.validity.rangeUnderflow'))
        expect_field_error(self.page.locator('#id_date'))
        self.assertFalse(ProductionRecord.objects.exists())
