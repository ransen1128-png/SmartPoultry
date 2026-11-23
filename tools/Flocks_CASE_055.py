"""Verify that a duplicate Flock ID is rejected when editing a live test flock."""

import os
import unittest



try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_055_duplicate_flock_id_update(self):
        """CASE-055 | Flock update failed & duplicate Flock ID error shown."""
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

            flock_id = read_test_value('SMARTPOULTRY_TEST_FLOCK_ID', 'Fixture flock ID: ')
            page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
            notification = page.locator('dialog#appDialog[open]')
            if notification.is_visible():
                notification.get_by_role('button', name='Close notification').click()
            expect(notification).to_be_hidden()

            row = page.locator('#flocksBody tr').filter(
                has=page.get_by_role('cell', name=flock_id, exact=True),
            )
            expect(row).to_be_visible()
            row.get_by_role('button', name='Edit', exact=True).click()
            modal = page.locator('#addFlockModal')
            expect(modal.get_by_role('heading', name='Edit Flock', exact=True)).to_be_visible()
            identifier = modal.locator('[name="flock_id"]')
            expect(identifier).to_have_value(flock_id)
            if identifier.evaluate('field => field.readOnly'):
                self.skipTest('Assigned flock IDs cannot be edited.')
            duplicate_id = read_test_value('SMARTPOULTRY_TEST_DUPLICATE_FLOCK_ID', 'Fixture flock ID: ')
            self.assertNotEqual(flock_id, duplicate_id)
            duplicate_row = page.locator('#flocksBody tr').filter(
                has=page.get_by_role('cell', name=duplicate_id, exact=True),
            )
            expect(duplicate_row).to_have_count(1)
            self.assertEqual(
                row.get_by_role('cell').first.inner_text(),
                duplicate_row.get_by_role('cell').first.inner_text(),
                'Both test flocks must belong to the same branch',
            )

            identifier.fill(duplicate_id)
            modal.get_by_label('Reason for correction', exact=True).fill('CASE-055 duplicate ID validation')
            modal.get_by_role('button', name='Update Flock', exact=True).click()

            expected_error = 'This flock ID is already used in this branch.'
            error = notification.locator('#appDialogText')
            expect(error).to_contain_text(expected_error)
            expect(error).to_be_visible()
            expect(modal).to_be_visible()

            page.reload(wait_until='domcontentloaded')
            expect(row).to_have_count(1)
            expect(duplicate_row).to_have_count(1)
            row.get_by_role('button', name='Edit', exact=True).click()
            expect(identifier).to_have_value(flock_id)
            print(f'Actual result: {expected_error} Both original IDs remain saved.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
