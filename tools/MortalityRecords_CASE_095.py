"""Mortality Records browser test CASE-095."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["95", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase095(MortalityRecordsBrowserCase):
    def test_case_095_back_returns_to_mortality_records(self):
        self.open_add_form()
        self.page.locator('main .page-heading').get_by_role('link', name='Back').click()
        expect(self.page).to_have_url(self.records_url)
        expect(self.page.get_by_role('heading', name='Mortality Records', exact=True)).to_be_visible()
