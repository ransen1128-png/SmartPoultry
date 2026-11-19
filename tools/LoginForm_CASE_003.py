"""Run the empty-password login case against the deployed site."""

import unittest

from playwright.sync_api import expect, sync_playwright


LOGIN_URL = 'https://smartpoultry-l3qo.onrender.com/login/'


class LiveLoginTests(unittest.TestCase):
    def test_case_003_empty_password(self):
        """CASE-003 | Leaving password empty prevents login and shows a validation error."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                response = page.goto(LOGIN_URL, timeout=90_000)
                self.assertIsNotNone(response)
                self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

                password = page.get_by_label('Password', exact=True)
                page.get_by_label('Email', exact=True).fill('login-test@example.com')
                password.fill('')

                # Capture the native validation event triggered by clicking Login.
                password.evaluate('''input => input.addEventListener('invalid', () => {
                    input.dataset.testValidationMessage = input.validationMessage;
                }, { once: true })''')
                page.get_by_role('button', name='Login', exact=True).click()

                expect(password).to_be_focused()
                expect(page).to_have_url(LOGIN_URL)
                self.assertTrue(password.evaluate('input => input.validity.valueMissing'))
                message = password.get_attribute('data-test-validation-message')
                self.assertTrue(message, 'The browser did not report a required-field validation error')
                print(f'\nActual result: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
