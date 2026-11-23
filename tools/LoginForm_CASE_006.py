"""Run the admin invalid-email login case against the deployed site."""

import unittest

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url


LOGIN_URL = f'{live_base_url()}/login/'


class LiveLoginTests(unittest.TestCase):
    def test_case_006_admin_invalid_email(self):
        """CASE-006 | An admin enters a malformed email and sees the inline email validation error."""
        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
            try:
                page = browser.new_page(locale='en-US')
                response = page.goto(LOGIN_URL, timeout=90_000)
                self.assertIsNotNone(response)
                self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

                email = page.get_by_label('Email', exact=True)
                email.fill('invalid-email@')
                page.get_by_label('Password', exact=True).fill('SyntheticTestPassword123!')

                page.get_by_role('button', name='Login', exact=True).click()

                expect(email).to_be_focused()
                expect(page).to_have_url(LOGIN_URL)
                self.assertTrue(email.evaluate('input => input.validity.typeMismatch'))
                error = page.locator('#emailError')
                expect(error).to_be_visible()
                expect(error).to_have_text('Enter a valid email address.')
                message = error.inner_text()
                print(f'\nActual result: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
