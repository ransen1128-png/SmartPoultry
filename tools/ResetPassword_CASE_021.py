"""Verify that the deployed reset form updates the password and provides a return to login."""

import os
import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
RECOVERY_URL = f'{BASE_URL}/forgot-password/'


class LiveResetPasswordTests(unittest.TestCase):
    def test_case_021_valid_matching_passwords_return_to_login(self):
        """CASE-021 | Password reset successful, redirected to Login."""
        email = read_test_value('SMARTPOULTRY_TEST_EMAIL', 'Registered email for userx: ', secret=False)
        username = os.environ.get('SMARTPOULTRY_TEST_USERNAME') or 'userx'

        new_password = read_test_value('SMARTPOULTRY_TEST_NEW_PASSWORD', 'New password for the dedicated test account: ', secret=True)

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
            page.get_by_label('New Password', exact=True).fill(new_password)
            page.get_by_label('Confirm Password', exact=True).fill(new_password)
            page.get_by_role('button', name='Update Password', exact=True).click()

            expect(page).to_have_url(f'{BASE_URL}/reset-password/complete/')
            expect(page.get_by_role(
                'heading', name='Password Updated Successfully!', exact=True,
            )).to_be_visible()

            confirmation = page.get_by_role('dialog', name='Password Changed Successfully!', exact=True)
            if confirmation.is_visible():
                confirmation.get_by_role('button', name='Close notification').click()
            page.get_by_role('link', name='Go to Login', exact=True).click()
            expect(page).to_have_url(f'{BASE_URL}/login/')
            expect(page.get_by_role('button', name='Login', exact=True)).to_be_visible()
            print('\nActual result: Password reset succeeded and Go to Login opened the login page.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
