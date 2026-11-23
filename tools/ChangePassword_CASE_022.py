"""Verify that an admin cannot change their password using a wrong current password."""

import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()


class LiveChangePasswordTests(unittest.TestCase):
    def test_case_022_admin_incorrect_current_password(self):
        """CASE-022 | Password update failed & error message shown."""
        email = read_test_value('SMARTPOULTRY_TEST_ADMIN_EMAIL', 'Admin test email: ', secret=False)
        password = read_test_value('SMARTPOULTRY_TEST_ADMIN_PASSWORD', 'Admin test password: ', secret=True)
        wrong_password = f'Wrong-{uuid4().hex}'
        new_password = f'New!7-{uuid4().hex}'

        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
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
                page.get_by_label('Current Password', exact=True).fill(wrong_password)
                page.get_by_label('New Password', exact=True).fill(new_password)
                page.get_by_label('Confirm Password', exact=True).fill(new_password)
                page.locator('form.settings-security-form button[type="submit"]').click()

                error = page.get_by_text('Current password is incorrect.', exact=True).filter(visible=True)
                expect(error).to_be_visible()
                expect(page).to_have_url(f'{BASE_URL}/settings/')
                sign_in()
                print('\nActual result: Current password is incorrect. The original password still works.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
