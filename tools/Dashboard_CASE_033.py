"""Dashboard browser test CASE-033."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["33", *sys.argv[1:]]))

from tools.farm_workflows_browser import DashboardWorkflowCase


class DashboardCase033(DashboardWorkflowCase):
    def test_case_033_dashboard(self):
        self.apply_dashboard(11)
        for label, value in (
            ('Total Revenue', '\u20b1332.00'), ('Total Expenses', '\u20b15358.00'), ('Net Profit', '\u20b1-5026.00'),
        ):
            self.expect_metric(label, value)
