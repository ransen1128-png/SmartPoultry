"""Settings browser test CASE-174."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["174", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.settings_browser import SettingsBrowserCase


class SettingsCase174(SettingsBrowserCase):
    def test_case_174_settings(self):
        panel = self.open_security()
        current = panel.get_by_label('Current Password', exact=True)
        current.fill('Fixture!123')
        expect(current).to_have_attribute('type', 'password')
        panel.get_by_role('button', name='Show current password', exact=True).click()
        expect(current).to_have_attribute('type', 'text')
        expect(current).to_have_value('Fixture!123')
        panel.get_by_role('button', name='Hide current password', exact=True).click()
        expect(current).to_have_attribute('type', 'password')
        expect(current).to_have_value('Fixture!123')
