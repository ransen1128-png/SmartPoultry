"""Mortality Records browser test CASE-077."""

from playwright.sync_api import expect
from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase077(MortalityRecordsBrowserCase):
    def test_case_077_quantity_above_live_count_rejected(self):
        self.fill_add_form(quantity='31')
        self.submit()
        expect(self.page.locator('main form')).to_contain_text(
            'Mortality quantity cannot exceed the selected flock quantity (30).',
        )
        self.assert_no_record_saved()
