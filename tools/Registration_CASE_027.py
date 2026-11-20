"""Verify that the live registration form rejects duplicate account details."""

import os
import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


REGISTER_URL = 'https://smartpoultry-l3qo.onrender.com/register/'


class LiveRegistrationTests(unittest.TestCase):
    def test_case_027_duplicate_username_or_email(self):
        """CASE-027 | Registration failed & duplicate account error shown."""
        registered_username = os.environ.get('SMARTPOULTRY_TEST_USERNAME') or 'userx'
        registered_email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or input('Registered test email: ')
        unique = f'case-027-{uuid4().hex}'
        scenarios = (
            (registered_username, f'{unique}@example.invalid', 'Username already taken.'),
            (unique, registered_email, 'Email already registered.'),
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                for username, email, expected_error in scenarios:
                    with self.subTest(expected_error=expected_error):
                        page.goto(REGISTER_URL, timeout=90_000, wait_until='domcontentloaded')
                        page.get_by_label('Username', exact=True).fill(username)
                        page.get_by_label('Email', exact=True).fill(email)
                        for label in ('Password', 'Confirm Password'):
                            page.get_by_label(label, exact=True).fill('Synthetic!027Password')
                        for number, answer in enumerate(('Synthetic cedar answer', 'Synthetic maple answer'), start=1):
                            page.get_by_label(f'Recovery Question {number}', exact=True).select_option(index=number - 1)
                            page.get_by_label(f'Answer {number}', exact=True).fill(answer)

                        page.get_by_role('button', name='Register', exact=True).click()
                        expect(page.locator('.alert-danger')).to_have_text(expected_error)
                        expect(page.locator('.alert-danger')).to_be_visible()
                        expect(page).to_have_url(REGISTER_URL)
                        print(f'Actual result: {expected_error}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
