"""Settings browser test CASE-175."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["175", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.settings_browser import SettingsBrowserCase


class SettingsCase175(SettingsBrowserCase):
    def test_case_175_settings(self):
        panel = self.open_preferences()
        for name in ('Email alerts', 'Email notifications', 'In-app notifications', 'Push notifications'):
            expect(panel.get_by_role('switch', name=name)).to_be_visible()
