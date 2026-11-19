"""Verify that the deployed reset form rejects an unregistered email."""

import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
NO_ACCOUNT_MESSAGE = 'No account was found with that email address.'


class LiveForgotPasswordTests(unittest.TestCase):
    def test_case_011_unregistered_email(self):
        """CASE-011 | An unregistered email shows an alert and stops password recovery."""
        email = f'case-011-{uuid4().hex}@example.invalid'
        password = 'SyntheticResetPassword123!'

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
                page.get_by_role('link', name='Forgot Password?').click()
                expect(page).to_have_url(f'{BASE_URL}/forgot-password/')

                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('New Password', exact=True).fill(password)
                page.get_by_label('Confirm Password', exact=True).fill(password)
                page.get_by_role('button', name='Reset Password', exact=True).click()

                alert = page.locator('.alert-danger')
                expect(alert).to_have_text(NO_ACCOUNT_MESSAGE, timeout=30_000)
                expect(alert).to_be_visible()
                expect(page).to_have_url(f'{BASE_URL}/forgot-password/')
                expect(page.locator('.alert-success')).to_have_count(0)
                print(f'\nActual result: {NO_ACCOUNT_MESSAGE}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
