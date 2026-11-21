"""Verify that closing the Add New Flock form discards the unsaved flock."""

from getpass import getpass
import os
import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_045_close_without_saving(self):
        """CASE-045 | Form closes & no new flock is added."""
        email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or 'userx@gmail.com'
        password = os.environ.get('SMARTPOULTRY_TEST_PASSWORD') or getpass('Test account password: ')

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill(password)
                page.get_by_role('button', name='Login', exact=True).click()
                expect(page).to_have_url(f'{BASE_URL}/dashboard/', timeout=30_000)

                page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
                expect(page).to_have_url(FLOCKS_URL)
                notification = page.locator('dialog#appDialog[open]')
                flock_id = f'QA-045-{uuid4().hex[:10]}'
                modal = page.locator('#addFlockModal')
                form = modal.locator('#addFlockForm')

                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()
                page.get_by_role('button', name='Add New Flock').click()
                branch = form.locator('select[name="branch"]')
                branch.select_option(index=1)

                form.locator('[name="flock_id"]').fill(flock_id)
                form.locator('[name="breed"]').select_option('layers')
                form.locator('[name="acquisition_source"]').select_option('own')
                form.locator('[name="quantity"]').fill('10')
                form.locator('[name="status"]').select_option('active')

                row = page.locator('#flocksBody tr').filter(
                    has=page.get_by_role('cell', name=flock_id, exact=True),
                )
                expect(row).to_have_count(0)
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
                expect(row).to_have_count(0)
                with page.expect_response(
                    lambda response: response.url == f'{BASE_URL}/api/flocks/'
                    and response.request.method == 'GET'
                ) as reload_response:
                    page.reload(wait_until='domcontentloaded')
                self.assertTrue(reload_response.value.ok, 'Could not reload the flock list')
                self.assertFalse(creation_requests, 'Closing the form sent a flock creation request')
                self.assertNotIn(flock_id, reload_response.value.text())
                expect(row).to_have_count(0)
                print(f'Actual result: The form closed and unsaved flock {flock_id} was absent after reload.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
