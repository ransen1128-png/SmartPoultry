"""Forecasting browser test CASE-139."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["139", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.forecasting_browser import ForecastingBrowserCase


class ForecastingCase139(ForecastingBrowserCase):
    def test_case_139_all_branches_shows_seventy_five_kg_inventory(self):
        self.distribution_fixture()
        self.open_forecasting()
        self.apply_branch(self.branch)
        self.apply_branch(None)
        expect(self.page.locator('.page-heading p')).to_contain_text('All branches')
        stock = self.page.get_by_text('Farm feed inventory:', exact=False)
        expect(stock).to_contain_text('75 kg')
        expect(stock).to_be_visible()
