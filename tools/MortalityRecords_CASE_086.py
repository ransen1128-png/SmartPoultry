"""Mortality Records browser test CASE-086."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["86", *sys.argv[1:]]))

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase086(MortalityRecordsBrowserCase):
    def test_case_086_date_required(self):
        self.fill_add_form(date='')
        self.submit()
        self.assert_required('#id_date')
        self.assert_no_record_saved()
