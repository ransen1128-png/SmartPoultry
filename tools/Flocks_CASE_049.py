"""Verify that the live form rejects a duplicate Flock ID in the same branch."""

import os
import unittest
from uuid import uuid4


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_049_duplicate_flock_id(self):
        """CASE-049 | Flock creation failed & duplicate Flock ID error shown."""
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
            flock_id = f'QA-042-{uuid4().hex[:10]}'
            modal = page.locator('#addFlockModal')
            form = modal.locator('#addFlockForm')

            def submit_flock():
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()
                page.get_by_role('button', name='Add New Flock').click()
                branch = form.locator('select[name="branch"]')
                branch.select_option(index=1)
                identifier = form.locator('[name="flock_id"]')
                if identifier.evaluate('field => field.readOnly'):
                    self.skipTest('Flock IDs are assigned automatically; manual duplicates cannot be entered.')
                identifier.fill(flock_id)
                form.locator('[name="breed"]').select_option('layers')
                form.locator('[name="acquisition_source"]').select_option('own')
                form.locator('[name="quantity"]').fill('10')
                modal.get_by_role('button', name='Save Flock', exact=True).click()

            submit_flock()
            row = page.locator('#flocksBody tr').filter(
                has=page.get_by_role('cell', name=flock_id, exact=True),
            )
            expect(row).to_have_count(1)
            expect(modal).to_be_hidden()
            print(f'Created test flock: {flock_id}', flush=True)

            submit_flock()
            error = 'This flock ID is already used in this branch.'
            expect(notification.locator('#appDialogText')).to_contain_text(error)
            expect(notification).to_be_visible()
            expect(modal).to_be_visible()
            expect(row).to_have_count(1)
            page.reload(wait_until='domcontentloaded')
            expect(row).to_have_count(1)
            print(f'Actual result: {error}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
