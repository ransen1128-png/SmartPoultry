"""Verify that the live registration form accepts valid details and redirects to login."""

import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url, live_base_url
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url, live_base_url


REGISTER_URL = f'{live_base_url()}/register/'
LOGIN_URL = f'{live_base_url()}/login/'


class LiveRegistrationTests(unittest.TestCase):
    def test_case_031_valid_details_redirect_to_login(self):
        """CASE-031 | Registration successful & user proceeds to login page."""
        username = f'case-031-{uuid4().hex}'

        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
            try:
                page = browser.new_page(locale='en-US')
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
