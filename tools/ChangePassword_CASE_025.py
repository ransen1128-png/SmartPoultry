"""Verify a successful admin password change and restore the original password."""

from getpass import getpass
import os
import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
SUCCESS_MESSAGE = 'Password updated successfully.'


def sign_in(browser, email, password):
    page = browser.new_page()
    page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
    page.get_by_label('Email', exact=True).fill(email)
    page.get_by_label('Password', exact=True).fill(password)
    page.get_by_role('button', name='Login', exact=True).click()
    expect(page).to_have_url(f'{BASE_URL}/admin-dashboard/', timeout=30_000)
    return page


def update_password(page, current_password, new_password):
    page.goto(f'{BASE_URL}/settings/', wait_until='domcontentloaded')
    page.get_by_role('tab', name='Account Security', exact=True).click()
    page.get_by_label('Current Password', exact=True).fill(current_password)
    page.get_by_label('New Password', exact=True).fill(new_password)
    page.get_by_label('Confirm Password', exact=True).fill(new_password)
    page.locator('form.settings-security-form button[type="submit"]').click()


class LiveChangePasswordTests(unittest.TestCase):
    def test_case_025_admin_matching_valid_new_passwords(self):
        """CASE-025 | Password updated successfully & confirmation message shown."""
        email = os.environ.get('SMARTPOULTRY_TEST_ADMIN_EMAIL') or input('Admin test email: ')
        original = os.environ.get('SMARTPOULTRY_TEST_ADMIN_PASSWORD') or getpass('Admin test password: ')
        temporary = os.environ.get('SMARTPOULTRY_TEST_NEW_PASSWORD') or f'Case!025-{uuid4().hex}'
        self.assertNotEqual(temporary, original, 'The new password must differ from the current password.')

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = sign_in(browser, email, original)
                update_password(page, original, temporary)
                try:
                    expect(page.get_by_text(SUCCESS_MESSAGE, exact=True)).to_be_visible()
                    sign_in(browser, email, temporary)
                    print(f'\nActual result: {SUCCESS_MESSAGE} The temporary password worked at sign-in.')
                finally:
                    update_password(page, temporary, original)
                    expect(page.get_by_text(SUCCESS_MESSAGE, exact=True)).to_be_visible()
                    sign_in(browser, email, original)
                    print('Cleanup verified: The original password works at sign-in.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
