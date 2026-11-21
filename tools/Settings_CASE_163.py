"""Settings browser test CASE-163."""

from playwright.sync_api import expect

from tools.settings_browser import SettingsBrowserCase


class SettingsCase163(SettingsBrowserCase):
    def test_case_163_settings(self):
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
