"""Admin Operations Selenium test CASE-179."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['179', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.admin_operations_browser import AdminOperationsBrowserCase


class AdminOperationsCase179(AdminOperationsBrowserCase):
    def test_case_179_staff_login_opens_users_management(self):
        expect(self.users.get_by_role('heading', name='Users Management', exact=True)).to_be_visible()
