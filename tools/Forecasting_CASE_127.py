"""Forecasting browser test CASE-127."""

from playwright.sync_api import expect

from tools.forecasting_browser import ForecastingBrowserCase


class ForecastingCase127(ForecastingBrowserCase):
    def test_case_127_branch_scope_shows_fifty_kg_delivered(self):
        self.distribution_fixture()
        self.open_forecasting()
        self.apply_branch(self.branch)
        expect(self.page.locator('.page-heading p')).to_contain_text(self.branch.name)
        delivery = self.page.get_by_text('Feed delivered to this branch in the last six months:', exact=False)
        expect(delivery).to_contain_text('50 kg')
        expect(delivery).to_be_visible()
