"""Run the empty-email login case against the deployed site."""

import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url


LOGIN_URL = f'{live_base_url()}/login/'


class LiveLoginTests(unittest.TestCase):
    def test_case_002_empty_email(self):
        """CASE-002 | Leaving email empty prevents login and shows a validation error."""
        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            response = page.goto(LOGIN_URL, timeout=90_000)
            self.assertIsNotNone(response)
            self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

            email = page.get_by_label('Email', exact=True)
            email.fill('')
            page.get_by_label('Password', exact=True).fill('SyntheticTestPassword123!')

            page.get_by_role('button', name='Login', exact=True).click()

            expect(email).to_be_focused()
            expect(page).to_have_url(LOGIN_URL)
            self.assertTrue(email.evaluate('input => input.validity.valueMissing'))
            error = page.locator('#emailError')
            expect(error).to_be_visible()
            expect(error).to_have_text('Email is required.')
            message = error.inner_text()
            print(f'\nActual result: {message}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
