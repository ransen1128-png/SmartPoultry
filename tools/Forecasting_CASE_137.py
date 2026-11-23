"""Forecasting browser test CASE-137."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["137", *sys.argv[1:]]))

from tools.forecasting_browser import ForecastingBrowserCase


class ForecastingCase137(ForecastingBrowserCase):
    def test_case_137_current_month_does_not_count_as_completed(self):
        self.record_month(self.today)
        self.open_forecasting()
        self.assert_readiness(0)
