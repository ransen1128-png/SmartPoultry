"""Run the empty-email login case against the deployed site."""

import unittest

from playwright.sync_api import expect, sync_playwright


LOGIN_URL = 'https://smartpoultry-l3qo.onrender.com/login/'


class LiveLoginTests(unittest.TestCase):
    def test_case_002_empty_email(self):
        """CASE-002 | Leaving email empty prevents login and shows a validation error."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                response = page.goto(LOGIN_URL, timeout=90_000)
                self.assertIsNotNone(response)
                self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

                email = page.get_by_label('Email', exact=True)
                email.fill('')
                page.get_by_label('Password', exact=True).fill('SyntheticTestPassword123!')

                # Capture the native validation event triggered by clicking Login.
                email.evaluate('''input => input.addEventListener('invalid', () => {
                    input.dataset.testValidationMessage = input.validationMessage;
                }, { once: true })''')
                page.get_by_role('button', name='Login', exact=True).click()

                expect(email).to_be_focused()
                expect(page).to_have_url(LOGIN_URL)
                self.assertTrue(email.evaluate('input => input.validity.valueMissing'))
                message = email.get_attribute('data-test-validation-message')
                self.assertTrue(message, 'The browser did not report a required-field validation error')
                print(f'\nActual result: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
