"""Dashboard browser test CASE-166."""

from tools.farm_workflows_browser import DashboardWorkflowCase


class DashboardCase166(DashboardWorkflowCase):
    def test_case_166_dashboard(self):
        self.apply_dashboard(11)
        for label, value in (
            ('Total Revenue', '\u20b1332.00'), ('Total Expenses', '\u20b15358.00'), ('Net Profit', '\u20b1-5026.00'),
        ):
            self.expect_metric(label, value)
