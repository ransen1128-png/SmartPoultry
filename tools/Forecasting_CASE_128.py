"""Forecasting browser test CASE-128."""

from playwright.sync_api import expect

from tools.forecasting_browser import ForecastingBrowserCase


class ForecastingCase128(ForecastingBrowserCase):
    def test_case_128_all_branches_shows_seventy_five_kg_inventory(self):
        self.distribution_fixture()
        self.open_forecasting()
        self.apply_branch(self.branch)
        self.apply_branch(None)
        expect(self.page.locator('.page-heading p')).to_contain_text('All branches')
        stock = self.page.get_by_text('Farm feed inventory:', exact=False)
        expect(stock).to_contain_text('75 kg')
        expect(stock).to_be_visible()
