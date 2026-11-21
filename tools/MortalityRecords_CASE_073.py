"""Mortality Records browser test CASE-073."""

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase073(MortalityRecordsBrowserCase):
    def test_case_073_flock_required(self):
        self.fill_add_form(flock=False)
        self.submit()
        self.assert_required('#id_flock', 'Please select an item in the list.')
        self.assert_no_record_saved()
