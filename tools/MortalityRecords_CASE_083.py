"""Mortality Records browser test CASE-083."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["83", *sys.argv[1:]]))

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase083(MortalityRecordsBrowserCase):
    def test_case_083_branch_required(self):
        self.fill_add_form(branch=False, flock=False)
        self.submit()
        self.assert_required('#id_branch')
        self.assert_no_record_saved()
