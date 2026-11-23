"""Settings browser test CASE-173."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["173", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.settings_browser import SettingsBrowserCase


class SettingsCase173(SettingsBrowserCase):
    def test_case_173_settings(self):
        panel = self.open_security()
        labels = ('Current Password', 'New Password', 'Confirm Password')
        for label in labels:
            expect(panel.get_by_label(label, exact=True)).to_have_value('')
        submissions = []

        def track_update(request):
            if request.method == 'POST' and request.url.startswith(f'{self.live_server_url}/settings/'):
                submissions.append(request)

        self.page.on('request', track_update)
        panel.get_by_role('button', name='Update Password').click()
        for label in labels:
            with self.subTest(field=label):
                field = panel.get_by_label(label, exact=True)
                self.assertTrue(field.evaluate('field => field.validity.valueMissing'))
                expect(field).to_have_accessible_description('Please fill out this field.')
                error_id = field.get_attribute('aria-describedby')
                expect(panel.locator(f'#{error_id}')).to_be_visible()
        self.assertFalse(submissions, 'The blank password form was submitted')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Fixture!123'))
