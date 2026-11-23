"""SmartPoultry integration INT-016 (CASE-200)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['200', *sys.argv[1:]]))

from tools.forecasting_browser import ForecastingBrowserCase
import Forecasting_CASE_137 as workflow_1
from tools.automation_browser import expect


class IntegrationCase200(ForecastingBrowserCase):
    def test_int_016(self):
        workflow_1.ForecastingCase137.test_case_137_current_month_does_not_count_as_completed(self)
        for label in ('Revenue Forecast', 'Expected Profit', 'Production Forecast'):
            expect(self.metric(label).locator('strong')).to_have_text('\u2014')
