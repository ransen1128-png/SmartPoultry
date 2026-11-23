"""Verify that the live registration form rejects a password that fails complexity validation."""

import unittest
from uuid import uuid4


try:
    from tools.automation_browser import expect, launch_browser, live_base_url
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url


REGISTER_URL = f'{live_base_url()}/register/'
VALIDATION_MESSAGE = 'Use at least 8 characters with an uppercase letter, a lowercase letter, a number, and a special symbol.'


class LiveRegistrationTests(unittest.TestCase):
    def test_case_028_password_fails_complexity_validation(self):
        """CASE-028 | Registration failed & password validation error shown."""
        username = f'case-028-{uuid4().hex}'

        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            page.goto(REGISTER_URL, timeout=90_000, wait_until='domcontentloaded')
            page.get_by_label('Username', exact=True).fill(username)
            page.get_by_label('Email', exact=True).fill(f'{username}@example.invalid')
            password = page.get_by_label('Password', exact=True)
            password.fill('syntheticpassword')
            page.get_by_label('Confirm Password', exact=True).fill('syntheticpassword')
            password.evaluate('''input => input.addEventListener('invalid', () => {
                input.dataset.testValidationMessage = input.validationMessage;
            }, { once: true })''')
            for number, answer in enumerate(('Synthetic cedar answer', 'Synthetic maple answer'), start=1):
                page.get_by_label(f'Recovery Question {number}', exact=True).select_option(index=number - 1)
                page.get_by_label(f'Answer {number}', exact=True).fill(answer)

            page.get_by_role('button', name='Register', exact=True).click()

            expect(password).to_be_focused()
            expect(password).to_have_attribute('data-test-validation-message', VALIDATION_MESSAGE)
            expect(page).to_have_url(REGISTER_URL)
            print(f'Actual result: {VALIDATION_MESSAGE}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
