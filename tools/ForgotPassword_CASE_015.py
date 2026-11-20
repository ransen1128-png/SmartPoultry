"""Verify that a registered email and matching username proceed to recovery questions."""

import os
import unittest

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
RECOVERY_URL = f'{BASE_URL}/forgot-password/'


class LiveForgotPasswordTests(unittest.TestCase):
    def test_case_015_registered_email_and_matching_username(self):
        """CASE-015 | Verification successful & user proceeds to recovery questions."""
        email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or input('Registered email for userx: ')
        username = os.environ.get('SMARTPOULTRY_TEST_USERNAME') or 'userx'

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
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
