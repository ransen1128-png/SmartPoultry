"""Test recovery with an unregistered email and username on the deployed site."""

import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
RECOVERY_URL = f'{BASE_URL}/forgot-password/'
QUESTIONS_URL = f'{RECOVERY_URL}questions/'


class LiveForgotPasswordTests(unittest.TestCase):
    def test_case_011_unregistered_email_and_username(self):
        """CASE-011 | Verification failed & error message shown."""
        username = f'case-011-{uuid4().hex}'
        email = f'{username}@example.invalid'

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
                expect(page).to_have_url(QUESTIONS_URL)

                page.locator('#answer_1').fill('Synthetic field trip answer')
                page.locator('#answer_2').fill('Synthetic toy answer')
                page.get_by_role('button', name='Verify Answers', exact=True).click()

                alert = page.get_by_role('alert')
                expect(alert).to_be_visible()
                expect(alert).to_contain_text('The answers could not be verified.')
                expect(page).to_have_url(QUESTIONS_URL)
                print(f'\nActual result: {alert.inner_text()}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
