"""Admin Operations Selenium test CASE-177."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['177', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.admin_operations_browser import AdminOperationsBrowserCase


class AdminOperationsCase177(AdminOperationsBrowserCase):
    def test_case_177_search_without_matches(self):
        self.search_users('qa-no-matching-user')
        expect(self.users.locator('tbody')).to_contain_text('No users found.')
