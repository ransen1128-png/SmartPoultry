"""Verify that the live registration form rejects duplicate recovery answers."""

import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


REGISTER_URL = 'https://smartpoultry-l3qo.onrender.com/register/'
DUPLICATE_ANSWER_MESSAGE = 'Use a different answer for each question.'


class LiveRegistrationTests(unittest.TestCase):
    def test_case_031_duplicate_recovery_answers(self):
        """CASE-031 | Registration failed & duplicate recovery answer error shown."""
        username = f'case-031-{uuid4().hex}'

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                page.goto(REGISTER_URL, timeout=90_000, wait_until='domcontentloaded')
                page.get_by_label('Username', exact=True).fill(username)
                page.get_by_label('Email', exact=True).fill(f'{username}@example.invalid')
                page.get_by_label('Password', exact=True).fill('Synthetic!031Password')
                confirmation = page.get_by_label('Confirm Password', exact=True)
                confirmation.fill('Synthetic!031Password')
                for number in (1, 2):
                    page.get_by_label(f'Recovery Question {number}', exact=True).select_option(index=number - 1)
                    page.get_by_label(f'Answer {number}', exact=True).fill('Synthetic cedar answer')

                page.get_by_role('button', name='Register', exact=True).click()

                error = page.get_by_text(DUPLICATE_ANSWER_MESSAGE, exact=True).filter(visible=True)
                expect(error.first).to_be_visible()
                expect(page).to_have_url(REGISTER_URL)
                print(f'Actual result: {DUPLICATE_ANSWER_MESSAGE}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
