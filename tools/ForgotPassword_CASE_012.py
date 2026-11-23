"""Verify that a registered email and username proceed to recovery questions."""

import os
import unittest

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
RECOVERY_URL = f'{BASE_URL}/forgot-password/'


class LiveForgotPasswordTests(unittest.TestCase):
    def test_case_012_registered_email_and_username(self):
        """CASE-012 | Verification successful & user proceeds to recovery questions."""
        email = read_test_value('SMARTPOULTRY_TEST_EMAIL', 'Registered email for userx: ', secret=False)
        username = os.environ.get('SMARTPOULTRY_TEST_USERNAME') or 'userx'

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

                expect(page).to_have_url(f'{RECOVERY_URL}questions/')
                expect(page.get_by_role('heading', name='Answer Your Recovery Questions', exact=True)).to_be_visible()
                expect(page.locator('#answer_1')).to_be_visible()
                expect(page.locator('#answer_2')).to_be_visible()
                expect(page.get_by_role('button', name='Verify Answers', exact=True)).to_be_visible()
                print('\nActual result: The recovery questions page appeared.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
