"""Test recovery with a registered email and an incorrect username."""

import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url, read_test_value


RECOVERY_URL = f'{live_base_url()}/forgot-password/'


class LiveForgotPasswordTests(unittest.TestCase):
    def test_case_013_registered_email_and_incorrect_username(self):
        """CASE-013 | Verification failed & user cannot proceed."""
        email = read_test_value('SMARTPOULTRY_TEST_EMAIL', 'Registered email for userx: ', secret=False)
        wrong_username = f'case-013-{uuid4().hex}'

        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
            try:
                page = browser.new_page(locale='en-US')
                page.goto(RECOVERY_URL, timeout=90_000, wait_until='domcontentloaded')
                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('Username', exact=True).fill(wrong_username)
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
