"""Mortality Records browser test CASE-075."""

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase075(MortalityRecordsBrowserCase):
    def test_case_075_date_required(self):
        self.fill_add_form(date='')
        self.submit()
        self.assert_required('#id_date', 'Please fill out this field.')
        self.assert_no_record_saved()
