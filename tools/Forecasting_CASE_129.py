"""Forecasting browser test CASE-129."""

from playwright.sync_api import expect

from tools.forecasting_browser import ForecastingBrowserCase


class ForecastingCase129(ForecastingBrowserCase):
    def test_case_129_feed_demand_for_forty_seven_chickens(self):
        self.flock.quantity = 47
        self.flock.save(update_fields=['quantity'])
        self.open_forecasting()
        self.apply_branch(self.branch)
        demand = self.metric('Feed Demand')
        expect(demand.locator('strong')).to_have_text('169.20 kg')
        expect(demand.locator('small')).to_have_text('30-day estimate at 0.12 kg per live chicken daily')
