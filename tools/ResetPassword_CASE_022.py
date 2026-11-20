"""Verify that the deployed reset form updates the password and provides a return to login."""

from getpass import getpass
import os
import unittest

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
RECOVERY_URL = f'{BASE_URL}/forgot-password/'
DEFAULT_TEST_NEW_PASSWORD = 'Az123123.'


class LiveResetPasswordTests(unittest.TestCase):
    def test_case_022_valid_matching_passwords_return_to_login(self):
        """CASE-022 | Password reset successful, redirected to Login."""
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

                for number in (1, 2):
                    field_id = f'answer_{number}'
                    question = page.locator(f'label[for="{field_id}"]').inner_text()
                    answer = os.environ.get(f'SMARTPOULTRY_TEST_RECOVERY_ANSWER_{number}') or getpass(
                        f'Correct test answer for "{question}": ',
                    )
                    page.locator(f'#{field_id}').fill(answer)
                page.get_by_role('button', name='Verify Answers', exact=True).click()

                expect(page).to_have_url(f'{RECOVERY_URL}new-password/')
                expect(page.get_by_role('heading', name='Choose a New Password', exact=True)).to_be_visible()
                new_password = os.environ.get('SMARTPOULTRY_TEST_NEW_PASSWORD') or DEFAULT_TEST_NEW_PASSWORD
                page.get_by_label('New Password', exact=True).fill(new_password)
                page.get_by_label('Confirm Password', exact=True).fill(new_password)
                page.get_by_role('button', name='Update Password', exact=True).click()

                expect(page).to_have_url(f'{BASE_URL}/reset-password/complete/')
                expect(page.get_by_role(
                    'heading', name='Password Updated Successfully!', exact=True,
                )).to_be_visible()

                page.get_by_role('link', name='Go to Login', exact=True).click()
                expect(page).to_have_url(f'{BASE_URL}/login/')
                expect(page.get_by_role('button', name='Login', exact=True)).to_be_visible()
                print('\nActual result: Password reset succeeded and Go to Login opened the login page.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
