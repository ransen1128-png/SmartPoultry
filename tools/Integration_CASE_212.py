"""SmartPoultry integration INT-028 (CASE-212)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['212', *sys.argv[1:]]))

from tools.admin_operations_browser import AdminOperationsBrowserCase
import AdminOperations_CASE_184 as workflow_1


class IntegrationCase212(AdminOperationsBrowserCase):
    def test_int_028(self):
        workflow_1.AdminOperationsCase184.test_case_184_staff_view_permission_reproduction(self)
