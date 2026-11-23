"""Settings browser test CASE-176."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["176", *sys.argv[1:]]))

from playwright.sync_api import expect

from notifications.models import NotificationPreference
from tools.settings_browser import SettingsBrowserCase


class SettingsCase176(SettingsBrowserCase):
    def test_case_176_settings(self):
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
