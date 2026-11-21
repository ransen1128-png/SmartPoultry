"""Mortality Records browser test CASE-074."""

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase074(MortalityRecordsBrowserCase):
    def test_case_074_quantity_required(self):
        self.fill_add_form(quantity='')
        self.submit()
        self.assert_required('#id_quantity', 'Please fill out this field.')
        self.assert_no_record_saved()
