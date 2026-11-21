"""Settings browser test CASE-164."""

from playwright.sync_api import expect

from tools.settings_browser import SettingsBrowserCase


class SettingsCase164(SettingsBrowserCase):
    def test_case_164_settings(self):
        panel = self.open_preferences()
        for name in ('Email alerts', 'Email notifications', 'In-app notifications', 'Push notifications'):
            expect(panel.get_by_role('switch', name=name)).to_be_visible()
