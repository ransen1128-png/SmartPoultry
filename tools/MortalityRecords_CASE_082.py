"""Mortality Records browser test CASE-082."""

from playwright.sync_api import expect

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase082(MortalityRecordsBrowserCase):
    def test_case_082_correction_reduces_live_count_to_27(self):
        record = self.accident_fixture()
        self.page.goto(self.records_url)
        self.record_row(record).get_by_role('link', name='Edit').click()
        self.page.locator('#id_quantity').fill('3')
        self.page.get_by_label('Reason for correction', exact=True).fill('Corrected the test mortality count.')
        self.submit()
        expect(self.page).to_have_url(self.records_url)

        expect(self.record_row(record).get_by_role('cell').nth(3)).to_have_text('3')
        record.refresh_from_db()
        self.flock.refresh_from_db()
        self.assertEqual(record.quantity, 3)
        self.assertEqual(self.flock.quantity, 27)
