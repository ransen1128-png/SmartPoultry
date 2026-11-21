"""Production Records browser test CASE-071."""

from playwright.sync_api import expect

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase071(ProductionRecordsBrowserCase):
    def test_case_071_cancel_egg_record_deletion(self):
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
