"""Run the admin empty-password login case against the deployed site."""

import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url


LOGIN_URL = f'{live_base_url()}/login/'


class LiveLoginTests(unittest.TestCase):
    def test_case_008_admin_empty_password(self):
        """CASE-008 | An admin leaves the password empty and sees a required-field error."""
        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            response = page.goto(LOGIN_URL, timeout=90_000)
            self.assertIsNotNone(response)
            self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

            password = page.get_by_label('Password', exact=True)
            page.get_by_label('Email', exact=True).fill('login-test@example.com')
            password.fill('')

            page.get_by_role('button', name='Login', exact=True).click()

            expect(password).to_be_focused()
            expect(page).to_have_url(LOGIN_URL)
            self.assertTrue(password.evaluate('input => input.validity.valueMissing'))
            error = page.locator('#passwordError')
            expect(error).to_be_visible()
            expect(error).to_have_text('Password is required.')
            print(f'\nActual result: {error.inner_text()}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
