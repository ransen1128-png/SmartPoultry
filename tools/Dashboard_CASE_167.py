"""Dashboard browser test CASE-167."""

from playwright.sync_api import expect

from tools.farm_workflows_browser import DashboardWorkflowCase


class DashboardCase167(DashboardWorkflowCase):
    def test_case_167_dashboard(self):
        self.apply_dashboard(11, self.branch)
        expect(self.page.locator('.page-heading')).to_contain_text('Overview of QA Sample Branch performance')
        for label, value in (
            ('Total Expenses', '\u20b12358.00'), ('Feed Cost', '\u20b12000.00'), ('Net Profit', '\u20b1-2026.00'),
        ):
            self.expect_metric(label, value)
