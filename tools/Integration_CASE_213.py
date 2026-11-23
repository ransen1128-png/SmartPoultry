"""SmartPoultry integration INT-029 (CASE-213)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['213', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.integration_workflows_browser import AccountIntegrationBrowserCase


class IntegrationCase213(AccountIntegrationBrowserCase):
    def test_int_029(self):
        self.page.driver.delete_all_cookies()
        self.login(self.user, self.original_password)
        expect(self.page).to_have_url(f'{self.live_server_url}/dashboard/')
        expect(self.page.get_by_role('heading', name='Dashboard', exact=True)).to_be_visible()
        expect(self.page.get_by_label('Farm branch').locator('option').filter(has_text=self.branch.name)).to_have_count(1)
