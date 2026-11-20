"""Run the successful login case against the deployed site."""

from getpass import getpass
import os
import unittest

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'


class LiveLoginTests(unittest.TestCase):
    def test_case_004_valid_credentials_redirect_to_dashboard(self):
        """CASE-004 | Valid credentials redirect to the Dashboard."""
        email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or input('Registered email for userx: ')
        password = os.environ.get('SMARTPOULTRY_TEST_PASSWORD') or getpass('Password for userx: ')

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                response = page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
                self.assertIsNotNone(response)
                self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill(password)
                page.get_by_role('button', name='Login', exact=True).click()

                expect(page).to_have_url(f'{BASE_URL}/dashboard/', timeout=30_000)
                expect(page.get_by_role('heading', name='Dashboard', exact=True)).to_be_visible()
                print('\nActual result: Login succeeded and the Dashboard appeared.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
