"""SmartPoultry integration INT-001 (CASE-185)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['185', *sys.argv[1:]]))

from tools.admin_operations_browser import AdminOperationsBrowserCase
import AdminOperations_CASE_179 as workflow_1


class IntegrationCase185(AdminOperationsBrowserCase):
    def test_int_001(self):
        workflow_1.AdminOperationsCase179.test_case_179_staff_login_opens_users_management(self)
