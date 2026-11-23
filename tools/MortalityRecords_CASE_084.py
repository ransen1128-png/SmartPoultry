"""Mortality Records browser test CASE-084."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["84", *sys.argv[1:]]))

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase084(MortalityRecordsBrowserCase):
    def test_case_084_flock_required(self):
        self.fill_add_form(flock=False)
        self.submit()
        self.assert_required('#id_flock')
        self.assert_no_record_saved()
