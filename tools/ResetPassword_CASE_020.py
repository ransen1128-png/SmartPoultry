"""Verify that the deployed reset form rejects mismatched passwords."""

import os
import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
RECOVERY_URL = f'{BASE_URL}/forgot-password/'


class LiveResetPasswordTests(unittest.TestCase):
    def test_case_020_new_password_does_not_match_confirmation(self):
        """CASE-020 | Reset fails with error message."""
        username = os.environ.get('SMARTPOULTRY_TEST_USERNAME') or 'userx'
        email = read_test_value('SMARTPOULTRY_TEST_EMAIL', f'Registered email for {username}: ', secret=False)

        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
            page.get_by_role('link', name='Forgot Password?', exact=True).click()
            expect(page).to_have_url(RECOVERY_URL)

            page.get_by_label('Email', exact=True).fill(email)
            page.get_by_label('Username', exact=True).fill(username)
            page.get_by_role('button', name='Continue', exact=True).click()
            expect(page).to_have_url(f'{RECOVERY_URL}questions/')

            for number in (1, 2):
                field_id = f'answer_{number}'
                question = page.locator(f'label[for="{field_id}"]').inner_text()
                answer = read_test_value(f'SMARTPOULTRY_TEST_RECOVERY_ANSWER_{number}', f'Correct test answer for "{question}": ', secret=True)
                page.locator(f'#{field_id}').fill(answer)
            page.get_by_role('button', name='Verify Answers', exact=True).click()

            expect(page).to_have_url(f'{RECOVERY_URL}new-password/')
            expect(page.get_by_role('heading', name='Choose a New Password', exact=True)).to_be_visible()
            page.get_by_label('New Password', exact=True).fill('SyntheticReset!6319Alpha')
            page.get_by_label('Confirm Password', exact=True).fill('SyntheticReset!6319Bravo')
            page.get_by_role('button', name='Update Password', exact=True).click()

            error = page.locator('#resetPasswordMatch')
            expect(error).to_be_visible()
            expect(error).to_have_text('Password not match')
            expect(page.get_by_label('Confirm Password', exact=True)).to_have_attribute('aria-invalid', 'true')
            expect(page).to_have_url(f'{RECOVERY_URL}new-password/')
            print(f'\nActual result: {error.inner_text()}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
