"""Run the admin invalid-email login case against the deployed site."""

import unittest

from playwright.sync_api import expect, sync_playwright


LOGIN_URL = 'https://smartpoultry-l3qo.onrender.com/login/'


class LiveLoginTests(unittest.TestCase):
    def test_case_006_admin_invalid_email(self):
        """CASE-006 | An admin enters a malformed email and sees Invalid email format."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                response = page.goto(LOGIN_URL, timeout=90_000)
                self.assertIsNotNone(response)
                self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

                email = page.get_by_label('Email', exact=True)
                email.fill('invalid-email@')
                page.get_by_label('Password', exact=True).fill('SyntheticTestPassword123!')

                # Capture the native validation event triggered by clicking Login.
                email.evaluate('''input => input.addEventListener('invalid', () => {
                    input.dataset.testValidationMessage = input.validationMessage;
                }, { once: true })''')
                page.get_by_role('button', name='Login', exact=True).click()

                expect(email).to_be_focused()
                expect(page).to_have_url(LOGIN_URL)
                self.assertTrue(email.evaluate('input => input.validity.typeMismatch'))
                message = email.get_attribute('data-test-validation-message')
                self.assertEqual(message, 'Invalid email format')
                print(f'\nActual result: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
