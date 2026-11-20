"""Test recovery with an unregistered email and a correct username."""

import os
import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


RECOVERY_URL = 'https://smartpoultry-l3qo.onrender.com/forgot-password/'


class LiveForgotPasswordTests(unittest.TestCase):
    def test_case_014_unregistered_email_and_correct_username(self):
        """CASE-014 | Verification failed & user cannot proceed."""
        username = os.environ.get('SMARTPOULTRY_TEST_USERNAME') or 'userx'
        email = f'case-014-{uuid4().hex}@example.invalid'

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                page.goto(RECOVERY_URL, timeout=90_000, wait_until='domcontentloaded')
                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('Username', exact=True).fill(username)
                page.get_by_role('button', name='Continue', exact=True).click()

                heading = page.get_by_role('heading', level=1).inner_text()
                print(f'\nActual result: {heading} ({page.url})')
                expect(page).to_have_url(RECOVERY_URL)
                error = page.locator('.errorlist:visible, .alert-danger:visible, [role="alert"]:visible').first
                expect(error).to_be_visible()
                print(f'Error shown: {error.inner_text()}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
