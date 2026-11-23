"""SmartPoultry integration INT-015 (CASE-199)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['199', *sys.argv[1:]]))

from tools.forecasting_browser import ForecastingBrowserCase
import Forecasting_CASE_140 as workflow_1
from tools.automation_browser import expect


class IntegrationCase199(ForecastingBrowserCase):
    def test_int_015(self):
        self.distribution_fixture()
        workflow_1.ForecastingCase140.test_case_140_feed_demand_for_forty_seven_chickens(self)
        delivery = self.page.get_by_text('Feed delivered to this branch in the last six months:')
        expect(delivery).to_contain_text('50 kg')
