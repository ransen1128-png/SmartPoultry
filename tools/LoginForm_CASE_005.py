"""Verify that the deployed login form rejects an incorrect password."""

import os
from secrets import token_urlsafe
import unittest

from playwright.sync_api import expect, sync_playwright


LOGIN_URL = 'https://smartpoultry-l3qo.onrender.com/login/'
INVALID_CREDENTIALS_MESSAGE = 'Invalid email or password. Please try again.'


class LiveLoginTests(unittest.TestCase):
    def test_case_005_correct_email_wrong_password(self):
        """CASE-005 | A wrong password shows the invalid-credentials message."""
        email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or input('Test account email: ')
        wrong_password = f'Incorrect-{token_urlsafe()}'

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                response = page.goto(LOGIN_URL, timeout=90_000, wait_until='domcontentloaded')
                self.assertIsNotNone(response)
                self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill(wrong_password)
                page.get_by_role('button', name='Login', exact=True).click()

                dialog = page.get_by_role('dialog', name='Login Failed')
                expect(dialog.get_by_text(INVALID_CREDENTIALS_MESSAGE, exact=True)).to_be_visible(
                    timeout=30_000,
                )
                expect(page).to_have_url(LOGIN_URL)
                print(f'\nActual result: {INVALID_CREDENTIALS_MESSAGE}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
