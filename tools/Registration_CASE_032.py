"""Verify that the live registration form accepts valid details and redirects to login."""

import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


REGISTER_URL = 'https://smartpoultry-l3qo.onrender.com/register/'
LOGIN_URL = 'https://smartpoultry-l3qo.onrender.com/login/'


class LiveRegistrationTests(unittest.TestCase):
    def test_case_032_valid_details_redirect_to_login(self):
        """CASE-032 | Registration successful & user proceeds to login page."""
        username = f'case-032-{uuid4().hex}'

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                page.goto(REGISTER_URL, timeout=90_000, wait_until='domcontentloaded')
                page.get_by_label('Username', exact=True).fill(username)
                page.get_by_label('Email', exact=True).fill(f'{username}@example.invalid')
                password = f'Registration!32-{uuid4().hex}'
                page.get_by_label('Password', exact=True).fill(password)
                confirmation = page.get_by_label('Confirm Password', exact=True)
                confirmation.fill(password)
                for number in (1, 2):
                    page.get_by_label(f'Recovery Question {number}', exact=True).select_option(index=number - 1)
                    page.get_by_label(f'Answer {number}', exact=True).fill(f'Test answer {number} {uuid4().hex}')

                page.get_by_role('button', name='Register', exact=True).click()

                expect(page).to_have_url(LOGIN_URL)
                expect(page.get_by_role('button', name='Login', exact=True)).to_be_visible()
                print(f'Actual result: Created {username} and redirected to Login.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
