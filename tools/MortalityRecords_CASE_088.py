"""Mortality Records browser test CASE-088."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["88", *sys.argv[1:]]))

from tools.automation_browser import expect

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase088(MortalityRecordsBrowserCase):
    def test_case_088_quantity_above_live_count_rejected(self):
        self.fill_add_form(quantity='31')
        self.submit()
        expect(self.page.locator('main form')).to_contain_text(
            'Mortality quantity cannot exceed the selected flock quantity (30).',
        )
        self.assert_no_record_saved()
