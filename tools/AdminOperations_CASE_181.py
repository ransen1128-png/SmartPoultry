"""Admin Operations Selenium test CASE-181."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['181', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.admin_operations_browser import AdminOperationsBrowserCase


class AdminOperationsCase181(AdminOperationsBrowserCase):
    def test_case_181_active_and_inactive_filters(self):
        self.search_users(self.sample.username)
        status = self.users.get_by_label('Status filter', exact=True)
        status.select_option('inactive')
        expect(self.page).to_have_url(
            f'{self.live_server_url}/admin-dashboard/?q={self.sample.username}&status=inactive',
        )
        expect(self.users.locator('tbody')).to_contain_text('No users found.')
        expect(self.sample_row()).to_have_count(0)
        status.select_option('active')
        expect(self.page).to_have_url(
            f'{self.live_server_url}/admin-dashboard/?q={self.sample.username}&status=active',
        )
        expect(self.sample_row()).to_be_visible()
