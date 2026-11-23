"""Verify that the deployed login form rejects an incorrect admin password."""

from secrets import token_urlsafe
import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


LOGIN_URL = f'{live_base_url()}/login/'
INVALID_CREDENTIALS_MESSAGE = 'Incorrect email or password. Please try again.'


class LiveLoginTests(unittest.TestCase):
    def test_case_010_correct_admin_email_wrong_password(self):
        """CASE-010 | A wrong admin password shows Invalid credentials."""
        email = read_test_value('SMARTPOULTRY_TEST_ADMIN_EMAIL', 'Admin test account email: ', secret=False)
        wrong_password = f'Incorrect-{token_urlsafe()}'

        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            response = page.goto(LOGIN_URL, timeout=90_000, wait_until='domcontentloaded')
            self.assertIsNotNone(response)
            self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

            page.get_by_label('Email', exact=True).fill(email)
            page.get_by_label('Password', exact=True).fill(wrong_password)
            page.get_by_role('button', name='Login', exact=True).click()

            expect(page.get_by_text(INVALID_CREDENTIALS_MESSAGE, exact=True)).to_be_visible(timeout=30_000)
            expect(page).to_have_url(LOGIN_URL)
            print(f'\nActual result: {INVALID_CREDENTIALS_MESSAGE}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
