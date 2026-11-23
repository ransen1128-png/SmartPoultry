"""SmartPoultry integration INT-031 (CASE-215)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['215', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.integration_workflows_browser import AccountIntegrationBrowserCase


class IntegrationCase215(AccountIntegrationBrowserCase):
    def test_int_031(self):
        self.page.goto(f'{self.live_server_url}/settings/')
        self.page.get_by_role('tab', name='Account Security', exact=True).click()
        self.page.get_by_label('Current Password', exact=True).fill(self.original_password)
        for label in ('New Password', 'Confirm Password'):
            self.page.get_by_label(label, exact=True).fill(self.new_password)
        self.page.get_by_role('button', name='Update Password', exact=True).click()
        expect(self.page.get_by_text('Password updated successfully.', exact=True).filter(visible=True)).to_be_visible()
        self.assert_password_replaced()
