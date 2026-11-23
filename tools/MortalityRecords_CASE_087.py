"""Mortality Records browser test CASE-087."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["87", *sys.argv[1:]]))

from tools.automation_browser import expect

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase087(MortalityRecordsBrowserCase):
    def test_case_087_zero_quantity_rejected(self):
        self.fill_add_form(quantity='0')
        self.submit()
        expect(self.page.locator('main form')).to_contain_text(
            'Mortality quantity must be greater than zero.',
        )
        self.assert_no_record_saved()
