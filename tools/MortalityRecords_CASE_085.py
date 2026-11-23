"""Mortality Records browser test CASE-085."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["85", *sys.argv[1:]]))

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase085(MortalityRecordsBrowserCase):
    def test_case_085_quantity_required(self):
        self.fill_add_form(quantity='')
        self.submit()
        self.assert_required('#id_quantity')
        self.assert_no_record_saved()
