"""Forecasting browser test CASE-125."""

from playwright.sync_api import expect

from core.branch_forecasting import add_months
from tools.forecasting_browser import ForecastingBrowserCase


class ForecastingCase125(ForecastingBrowserCase):
    def test_case_125_fewer_than_four_months_disables_forecasts(self):
        for offset in (-3, -2, -1):
            self.record_month(add_months(self.today.replace(day=1), offset))
        self.open_forecasting()
        self.assert_readiness(3)
        for name in ('Revenue Forecast', 'Expected Profit', 'Production Forecast'):
            expect(self.metric(name).locator('strong')).to_have_text('\u2014')
