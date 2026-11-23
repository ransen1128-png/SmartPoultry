"""Production Records browser test CASE-082."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["82", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase082(ProductionRecordsBrowserCase):
    def test_case_082_cancel_egg_record_deletion(self):
        record = self.egg_fixture()
        self.page.goto(self.records_url)
        row = self.record_row(record)
        row.get_by_role('button', name='Delete').click()
        dialog = self.page.locator('#appConfirmDialog')
        expect(dialog.get_by_text('Delete this production record?', exact=True)).to_be_visible()
        dialog.get_by_role('button', name='Cancel', exact=True).click()
        expect(dialog).to_be_hidden()
        expect(row).to_be_visible()
        self.page.reload(wait_until='domcontentloaded')
        expect(row).to_be_visible()
