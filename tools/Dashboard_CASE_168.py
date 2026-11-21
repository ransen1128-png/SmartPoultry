"""Dashboard browser test CASE-168."""

from playwright.sync_api import expect

from tools.farm_workflows_browser import DashboardWorkflowCase


class DashboardCase168(DashboardWorkflowCase):
    def test_case_168_dashboard(self):
        self.apply_dashboard(10)
        for label in ('Total Revenue', 'Total Expenses', 'Net Profit'):
            self.expect_metric(label, '\u20b10.00')
        expect(self.page.locator('#dashboardProduction strong')).to_have_text(['0', '0'])
        self.expect_metric('Total Chicken', '47')
