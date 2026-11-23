"""SmartPoultry integration INT-011 (CASE-195)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['195', *sys.argv[1:]]))

from tools.farm_workflows_browser import DashboardWorkflowCase
import Dashboard_CASE_033 as workflow_1


class IntegrationCase195(DashboardWorkflowCase):
    def test_int_011(self):
        workflow_1.DashboardCase033.test_case_033_dashboard(self)
