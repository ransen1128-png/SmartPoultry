"""Production Records browser test CASE-081."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["81", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase081(ProductionRecordsBrowserCase):
    def test_case_081_correct_egg_quantity(self):
        record = self.egg_fixture()
        self.open_egg_edit(record)
        self.page.locator('#id_quantity').fill('14')
        self.page.get_by_label('Reason for correction').fill('Corrected the test egg count.')
        self.submit()
        expect(self.page).to_have_url(self.records_url)
        cells = self.record_row(record).get_by_role('cell')
        expect(cells.nth(6)).to_have_text('14')
        expect(cells.nth(8)).to_have_text('14')
        record.refresh_from_db()
        self.assertEqual(record.quantity, 14)
