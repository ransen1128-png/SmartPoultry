"""Settings browser test CASE-165."""

from playwright.sync_api import expect

from notifications.models import NotificationPreference
from tools.settings_browser import SettingsBrowserCase


class SettingsCase165(SettingsBrowserCase):
    def test_case_165_settings(self):
        panel = self.open_preferences()
        switch = panel.get_by_role('switch', name='In-app notifications')
        expect(switch).to_be_checked()
        switch.uncheck()
        panel.get_by_role('button', name='Save Settings').click()
        message = self.page.get_by_text('Notification settings updated.', exact=True).filter(visible=True)
        expect(message).to_be_visible()
        self.page.reload(wait_until='domcontentloaded')
        expect(panel).to_be_visible()
        expect(switch).not_to_be_checked()
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(preference.in_app_notifications)
