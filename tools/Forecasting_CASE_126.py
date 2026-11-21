"""Forecasting browser test CASE-126."""

from tools.forecasting_browser import ForecastingBrowserCase


class ForecastingCase126(ForecastingBrowserCase):
    def test_case_126_current_month_does_not_count_as_completed(self):
        self.record_month(self.today)
        self.open_forecasting()
        self.assert_readiness(0)
