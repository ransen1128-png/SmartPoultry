"""Verify that the live registration form rejects duplicate recovery questions."""

import unittest
from uuid import uuid4


try:
    from tools.automation_browser import expect, launch_browser, live_base_url
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url


REGISTER_URL = f'{live_base_url()}/register/'
DUPLICATE_QUESTION_MESSAGE = 'Choose two different recovery questions.'


class LiveRegistrationTests(unittest.TestCase):
    def test_case_029_duplicate_recovery_question(self):
        """CASE-029 | Registration failed & duplicate recovery question error shown."""
        username = f'case-029-{uuid4().hex}'

        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            page.goto(REGISTER_URL, timeout=90_000, wait_until='domcontentloaded')
            page.get_by_label('Username', exact=True).fill(username)
            page.get_by_label('Email', exact=True).fill(f'{username}@example.invalid')
            page.get_by_label('Password', exact=True).fill('Synthetic!030Password')
            confirmation = page.get_by_label('Confirm Password', exact=True)
            confirmation.fill('Synthetic!030Password')
            for number, answer in enumerate(('Synthetic cedar answer', 'Synthetic maple answer'), start=1):
                page.get_by_label(f'Recovery Question {number}', exact=True).select_option(index=0)
                page.get_by_label(f'Answer {number}', exact=True).fill(answer)

            page.get_by_role('button', name='Register', exact=True).click()

            error = page.get_by_text(DUPLICATE_QUESTION_MESSAGE, exact=True).filter(visible=True)
            expect(error.first).to_be_visible()
            expect(page).to_have_url(REGISTER_URL)
            print(f'Actual result: {DUPLICATE_QUESTION_MESSAGE}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
