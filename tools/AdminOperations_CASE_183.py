"""Admin Operations Selenium test CASE-183."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['183', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.admin_operations_browser import AdminOperationsBrowserCase


class AdminOperationsCase183(AdminOperationsBrowserCase):
    def test_case_183_staff_profile_fields(self):
        self.page.locator('nav a[href="/profile/"]').filter(has_text='Admin Profile').click()
        expect(self.page).to_have_url(f'{self.live_server_url}/profile/')
        expect(self.page.get_by_role('heading', name='Manage Profile', exact=True)).to_be_visible()
        for label in ('First Name', 'Last Name', 'Username', 'Email', 'Phone'):
            with self.subTest(field=label):
                expect(self.page.get_by_label(label, exact=True)).to_be_visible()
