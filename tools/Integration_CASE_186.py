"""SmartPoultry integration INT-002 (CASE-186)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['186', *sys.argv[1:]]))

from tools.farm_workflows_browser import FlockWorkflowCase
import Flocks_CASE_066 as workflow_1


class IntegrationCase186(FlockWorkflowCase):
    def test_int_002(self):
        workflow_1.FlocksCase066.test_case_066_flocks(self)
