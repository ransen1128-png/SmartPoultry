"""Test recovery with an unregistered email and username on the deployed site."""

import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url


BASE_URL = live_base_url()
RECOVERY_URL = f'{BASE_URL}/forgot-password/'


class LiveForgotPasswordTests(unittest.TestCase):
    def test_case_011_unregistered_email_and_username(self):
        """CASE-011 | Verification failed & error message shown."""
        username = f'case-011-{uuid4().hex}'
        email = f'{username}@example.invalid'

        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
            try:
                page = browser.new_page(locale='en-US')
                page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
                page.get_by_role('link', name='Forgot Password?', exact=True).click()
                expect(page).to_have_url(RECOVERY_URL)

                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('Username', exact=True).fill(username)
                page.get_by_role('button', name='Continue', exact=True).click()
                alert = page.get_by_text('Email and username do not match an active account.', exact=True)
                expect(alert).to_be_visible()
                expect(page).to_have_url(RECOVERY_URL)
                print(f'\nActual result: {alert.inner_text()}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
