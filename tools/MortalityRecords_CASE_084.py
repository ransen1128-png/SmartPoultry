"""Mortality Records browser test CASE-084."""

from playwright.sync_api import expect

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase084(MortalityRecordsBrowserCase):
    def test_case_084_back_returns_to_mortality_records(self):
        self.open_add_form()
        self.page.locator('main .page-heading').get_by_role('link', name='Back').click()
        expect(self.page).to_have_url(self.records_url)
        expect(self.page.get_by_role('heading', name='Mortality Records', exact=True)).to_be_visible()
