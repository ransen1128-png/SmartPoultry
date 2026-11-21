"""Mortality Records browser test CASE-072."""

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase072(MortalityRecordsBrowserCase):
    def test_case_072_branch_required(self):
        self.fill_add_form(branch=False, flock=False)
        self.submit()
        self.assert_required('#id_branch', 'Please select an item in the list.')
        self.assert_no_record_saved()
