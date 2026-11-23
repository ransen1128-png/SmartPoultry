"""Verify that closing the Add New Flock form discards the unsaved flock."""

import os
import unittest

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_052_close_without_saving(self):
        """CASE-052 | Form closes & no new flock is added."""
        email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or 'userx@gmail.com'
        password = read_test_value('SMARTPOULTRY_TEST_PASSWORD', 'Test account password: ', secret=True)

        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
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
                modal = page.locator('#addFlockModal')
                form = modal.locator('#addFlockForm')

                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()
                page.get_by_role('button', name='Add New Flock').click()
                branch = form.locator('select[name="branch"]')
                branch.select_option(index=1)

                form.locator('[name="breed"]').select_option('layers')
                form.locator('[name="acquisition_source"]').select_option('own')
                form.locator('[name="quantity"]').fill('10')
                form.locator('[name="status"]').select_option('active')

                creation_requests = []

                def track_creation(request):
                    if request.url == f'{BASE_URL}/api/flocks/' and request.method == 'POST':
                        creation_requests.append(request)

                page.on('request', track_creation)
                modal.get_by_role('button', name='Close', exact=True).click()
                confirmation = page.locator('#appConfirmDialog')
                expect(confirmation.get_by_text('Discard unsaved changes?', exact=True)).to_be_visible()
                confirmation.get_by_role('button', name='Confirm', exact=True).click()
                expect(modal).to_be_hidden()
                self.assertFalse(creation_requests, 'Closing the form sent a flock creation request')
                print('Actual result: The form closed without sending a save request.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
