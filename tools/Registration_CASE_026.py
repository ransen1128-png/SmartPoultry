"""Verify that the live registration form rejects duplicate account details."""

import os
import unittest
from uuid import uuid4


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


REGISTER_URL = f'{live_base_url()}/register/'


class LiveRegistrationTests(unittest.TestCase):
    def test_case_026_duplicate_username_or_email(self):
        """CASE-026 | Registration failed & duplicate account error shown."""
        registered_username = os.environ.get('SMARTPOULTRY_TEST_USERNAME') or 'userx'
        registered_email = read_test_value('SMARTPOULTRY_TEST_EMAIL', 'Registered test email: ', secret=False)
        unique = f'case-026-{uuid4().hex}'
        scenarios = (
            (registered_username, f'{unique}@example.invalid', 'Username already taken.'),
            (unique, registered_email, 'Email already registered.'),
        )

        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            for username, email, expected_error in scenarios:
                with self.subTest(expected_error=expected_error):
                    page.goto(REGISTER_URL, timeout=90_000, wait_until='domcontentloaded')
                    page.get_by_label('Username', exact=True).fill(username)
                    page.get_by_label('Email', exact=True).fill(email)
                    for label in ('Password', 'Confirm Password'):
                        page.get_by_label(label, exact=True).fill('Synthetic!027Password')
                    for number, answer in enumerate(('Synthetic cedar answer', 'Synthetic maple answer'), start=1):
                        page.get_by_label(f'Recovery Question {number}', exact=True).select_option(index=number - 1)
                        page.get_by_label(f'Answer {number}', exact=True).fill(answer)

                    page.get_by_role('button', name='Register', exact=True).click()
                    alert = page.get_by_role('alert').get_by_text(expected_error, exact=True)
                    expect(alert).to_be_visible()
                    expect(page).to_have_url(REGISTER_URL)
                    print(f'Actual result: {expected_error}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
