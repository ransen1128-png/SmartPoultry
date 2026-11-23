"""Production Records browser test CASE-080."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["80", *sys.argv[1:]]))

from tools.automation_browser import expect

from production.models import ProductionRecord

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase080(ProductionRecordsBrowserCase):
    def test_case_080_record_five_meat_ready_chickens(self):
        self.fill_record(self.broilers, quantity='5')
        self.submit()
        expect(self.page).to_have_url(self.records_url)
        record = ProductionRecord.objects.get(flock=self.broilers)
        cells = self.record_row(record).get_by_role('cell')
        expect(cells.nth(3)).to_have_text('20')
        expect(cells.nth(4)).to_have_text('Meat Ready')
        expect(cells.nth(8)).to_have_text('5')
        self.broilers.refresh_from_db()
        self.assertEqual(self.broilers.quantity, 20)
