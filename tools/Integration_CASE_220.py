"""SmartPoultry integration INT-036 (CASE-220)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['220', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.forecasting_browser import ForecastingBrowserCase
from datetime import timedelta


class IntegrationCase220(ForecastingBrowserCase):
    def test_int_036(self):
        month = self.today.replace(day=1)
        for _ in range(5):
            month = (month - timedelta(days=1)).replace(day=1)
            self.record_month(month)
        self.open_forecasting()
        self.apply_branch(self.branch)
        readiness = self.page.get_by_role('listitem').filter(has_text='Random Forest trained')
        expect(readiness).to_have_count(3, timeout=20000)
        for label in ('Revenue Forecast', 'Expected Profit', 'Production Forecast'):
            expect(self.metric(label).locator('strong')).not_to_contain_text('—')
