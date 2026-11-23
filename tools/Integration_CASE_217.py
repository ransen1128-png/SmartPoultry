"""SmartPoultry integration INT-033 (CASE-217)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['217', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.settings_browser import SettingsBrowserCase
import Settings_CASE_176 as preference


class IntegrationCase217(SettingsBrowserCase):
    def test_int_033(self):
        preference.SettingsCase176.test_case_176_settings(self)
        self.open_inventory()
        self.fill_item()
        with self.page.expect_response(
            lambda response: response.url.endswith('/api/inventory/items/') and response.request.method == 'POST',
        ) as saved:
            self.page.get_by_role('button', name='Save Item').click()
        self.assertEqual(saved.value.status, 201)
        self.page.goto(f'{self.live_server_url}/notifications/')
        expect(self.page.get_by_role('heading', name='Notifications', exact=True)).to_be_visible()
        expect(self.page.locator('.notification-list li').filter(has_text=self.item_name)).to_have_count(0)
