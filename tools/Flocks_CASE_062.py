"""Verify that the automatic Flock ID field rejects typed characters."""

import os
import unittest



try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_062_reject_manual_flock_id_characters(self):
        """CASE-062 | Invalid characters rejected & only numeric Flock IDs allowed."""
        email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or 'userx@gmail.com'
        password = read_test_value('SMARTPOULTRY_TEST_PASSWORD', 'Test account password: ', secret=True)

        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
            page.get_by_label('Email', exact=True).fill(email)
            page.get_by_label('Password', exact=True).fill(password)
            page.get_by_role('button', name='Login', exact=True).click()
            expect(page).to_have_url(f'{BASE_URL}/dashboard/', timeout=30_000)

            page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
            expect(page).to_have_url(FLOCKS_URL)
            notification = page.locator('dialog#appDialog[open]')
            if notification.is_visible():
                notification.get_by_role('button', name='Close notification').click()
            expect(notification).to_be_hidden()

            page.get_by_role('button', name='Add New Flock').click()
            identifier = page.locator('#addFlockModal').get_by_label('Flock ID', exact=True)
            expect(identifier).to_be_visible()
            expect(identifier).to_have_value('')
            self.assertTrue(identifier.evaluate('field => field.readOnly'))

            identifier.focus()
            page.keyboard.type('ABC!@#')
            expect(identifier).to_have_value('')
            print('Actual result: The automatic Flock ID field rejected letters and special characters.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
