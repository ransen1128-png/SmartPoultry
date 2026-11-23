"""Dashboard browser test CASE-035."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["35", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.farm_workflows_browser import DashboardWorkflowCase


class DashboardCase035(DashboardWorkflowCase):
    def test_case_035_dashboard(self):
        self.apply_dashboard(10)
        for label in ('Total Revenue', 'Total Expenses', 'Net Profit'):
            self.expect_metric(label, '\u20b10.00')
        expect(self.page.locator('#dashboardProduction strong')).to_have_text(['0', '0'])
        self.expect_metric('Total Chicken', '47')
