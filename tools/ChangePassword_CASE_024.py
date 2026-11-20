"""Verify that the admin password form rejects mismatched new passwords."""

from getpass import getpass
import os
import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'


class LiveChangePasswordTests(unittest.TestCase):
    def test_case_024_admin_mismatched_new_passwords(self):
        """CASE-024 | Password mismatch error shown & password not updated."""
        email = os.environ.get('SMARTPOULTRY_TEST_ADMIN_EMAIL') or input('Admin test email: ')
        password = os.environ.get('SMARTPOULTRY_TEST_ADMIN_PASSWORD') or getpass('Admin test password: ')
        confirmation_password = f'Confirm!8-{uuid4().hex}'
        new_password = f'New!7-{uuid4().hex}'

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                def sign_in():
                    page = browser.new_page()
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
