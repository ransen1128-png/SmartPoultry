"""SmartPoultry integration INT-012 (CASE-196)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['196', *sys.argv[1:]]))

from tools.farm_workflows_browser import DashboardWorkflowCase
import Dashboard_CASE_034 as workflow_1


class IntegrationCase196(DashboardWorkflowCase):
    def test_int_012(self):
        workflow_1.DashboardCase034.test_case_034_dashboard(self)
        self.expect_metric('Total Revenue', '\u20b1332.00')
