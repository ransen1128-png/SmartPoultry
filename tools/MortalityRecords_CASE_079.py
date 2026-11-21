"""Mortality Records browser test CASE-079."""

from playwright.sync_api import expect

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase079(MortalityRecordsBrowserCase):
    def test_case_079_flock_disabled_before_branch_selection(self):
        self.open_add_form()
        expect(self.page.get_by_role('heading', name='Add Mortality Record', exact=True)).to_be_visible()
        expect(self.page.locator('#id_branch')).to_have_value('')
        flock = self.page.locator('#id_flock')
        expect(flock).to_be_disabled()
        expect(flock.locator('option:checked')).to_have_text('Choose a branch first')
