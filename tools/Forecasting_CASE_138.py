"""Forecasting browser test CASE-138."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["138", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.forecasting_browser import ForecastingBrowserCase


class ForecastingCase138(ForecastingBrowserCase):
    def test_case_138_branch_scope_shows_fifty_kg_delivered(self):
        self.distribution_fixture()
        self.open_forecasting()
        self.apply_branch(self.branch)
        expect(self.page.locator('.page-heading p')).to_contain_text(self.branch.name)
        delivery = self.page.get_by_text('Feed delivered to this branch in the last six months:', exact=False)
        expect(delivery).to_contain_text('50 kg')
        expect(delivery).to_be_visible()
