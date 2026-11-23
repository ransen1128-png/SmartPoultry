"""Admin Operations Selenium test CASE-180."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['180', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.admin_operations_browser import AdminOperationsBrowserCase


class AdminOperationsCase180(AdminOperationsBrowserCase):
    def test_case_180_search_finds_sample_user(self):
        self.search_users(self.sample.username)
        expect(self.users.locator('tbody tr')).to_have_count(1)
        expect(self.sample_row().get_by_text(self.sample.username, exact=True).first).to_be_visible()
