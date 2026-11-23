"""Verify that the admin password form rejects mismatched new passwords."""

import unittest
from uuid import uuid4


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()


class LiveChangePasswordTests(unittest.TestCase):
    def test_case_023_admin_mismatched_new_passwords(self):
        """CASE-023 | Password mismatch error shown & password not updated."""
        email = read_test_value('SMARTPOULTRY_TEST_ADMIN_EMAIL', 'Admin test email: ', secret=False)
        password = read_test_value('SMARTPOULTRY_TEST_ADMIN_PASSWORD', 'Admin test password: ', secret=True)
        confirmation_password = f'Confirm!8-{uuid4().hex}'
        new_password = f'New!7-{uuid4().hex}'

        browser = launch_browser()
        try:
            def sign_in():
                page = browser.new_page(locale='en-US')
                page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill(password)
                page.get_by_role('button', name='Login', exact=True).click()
                expect(page).to_have_url(f'{BASE_URL}/admin-dashboard/', timeout=30_000)
                return page

            page = sign_in()
            page.goto(f'{BASE_URL}/settings/', wait_until='domcontentloaded')
            page.get_by_role('tab', name='Account Security', exact=True).click()
            page.get_by_label('Current Password', exact=True).fill(password)
            page.get_by_label('New Password', exact=True).fill(new_password)
            page.get_by_label('Confirm Password', exact=True).fill(confirmation_password)
            page.locator('form.settings-security-form button[type="submit"]').click()

            error = page.get_by_text('New passwords do not match.', exact=True)
            expect(error).to_be_visible()
            expect(page).to_have_url(f'{BASE_URL}/settings/')
            sign_in()
            print('\nActual result: New passwords do not match. The original password still works.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
