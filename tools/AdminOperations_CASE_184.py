"""Admin Operations Selenium test CASE-184. Reproduces the open staff permission issue."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['184', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.admin_operations_browser import AdminOperationsBrowserCase


class AdminOperationsCase184(AdminOperationsBrowserCase):
    def test_case_184_staff_view_permission_reproduction(self):
        self.search_users(self.sample.username)
        view = self.sample_row().locator('a[title="View"]')
        expect(view).to_be_visible()
        target = self.live_server_url + view.get_attribute('href')
        with self.page.expect_response(
            lambda response: response.url == target and response.request.method == 'GET',
        ) as navigation:
            view.click()
        expect(self.page).to_have_url(target)
        self.assertEqual(navigation.value.status, 403, 'Staff View behavior changed. Review the permission rule.')
