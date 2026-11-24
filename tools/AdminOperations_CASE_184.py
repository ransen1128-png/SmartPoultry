"""Admin Operations Selenium test CASE-184. Staff without account permissions get no View link and no access."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['184', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.admin_operations_browser import AdminOperationsBrowserCase


class AdminOperationsCase184(AdminOperationsBrowserCase):
    def test_case_184_staff_view_permission(self):
        self.search_users(self.sample.username)
        expect(self.sample_row()).to_be_visible()
        expect(self.sample_row().locator('a[title="View"]')).to_have_count(0)
        target = f'{self.live_server_url}/admin/accounts/userprofile/{self.sample.pk}/change/'
        with self.page.expect_response(
            lambda response: response.url == target and response.request.method == 'GET',
        ) as navigation:
            self.page.goto(target)
        self.assertEqual(navigation.value.status, 403, 'Staff without account permissions must not open the account page.')
