"""Verify that one incorrect recovery answer blocks password reset."""

from getpass import getpass
import os
from uuid import uuid4
import unittest

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
RECOVERY_URL = f'{BASE_URL}/forgot-password/'


class LiveForgotPasswordTests(unittest.TestCase):
    def test_case_016_one_correct_and_one_incorrect_answer(self):
        """CASE-016 | Verification failed & user cannot proceed to password reset."""
        email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or input('Registered email for userx: ')
        username = os.environ.get('SMARTPOULTRY_TEST_USERNAME') or 'userx'

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
                page.get_by_role('link', name='Forgot Password?', exact=True).click()
                expect(page).to_have_url(RECOVERY_URL)

                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('Username', exact=True).fill(username)
                page.get_by_role('button', name='Continue', exact=True).click()

                expect(page).to_have_url(f'{RECOVERY_URL}questions/')
                expect(page.get_by_role('heading', name='Answer Your Recovery Questions', exact=True)).to_be_visible()
                expect(page.locator('#answer_1')).to_be_visible()
                expect(page.locator('#answer_2')).to_be_visible()
                expect(page.get_by_role('button', name='Verify Answers', exact=True)).to_be_visible()
                question = page.locator('label[for="answer_1"]').inner_text()
                correct_answer = os.environ.get('SMARTPOULTRY_TEST_RECOVERY_ANSWER_1') or getpass(
                    f'Correct test answer for "{question}": ',
                )
                page.locator('#answer_1').fill(correct_answer)
                page.locator('#answer_2').fill(f'Incorrect test answer {uuid4().hex}')
                page.get_by_role('button', name='Verify Answers', exact=True).click()

                alert = page.get_by_role('alert')
                expect(alert).to_contain_text('The answers could not be verified.')
                expect(alert).to_be_visible()
                expect(page).to_have_url(f'{RECOVERY_URL}questions/')
                print(f'\nActual result: {alert.inner_text()}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
