"""Verify that a valid edit is saved and displayed in Current Flocks."""

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
    def test_case_056_valid_flock_update(self):
        """CASE-056 | Flock updated successfully & changes displayed in the Current Flocks list."""
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
                quantity = modal.locator('[name="quantity"]')
                old_quantity = int(quantity.input_value())
                new_quantity = str(old_quantity + 2)
                quantity.fill(new_quantity)
                modal.get_by_label('Reason for correction', exact=True).fill('CASE-056 successful quantity correction')
                with page.expect_response(
                    lambda response: response.url.startswith(f'{BASE_URL}/api/flocks/')
                    and response.request.method == 'PATCH'
                ) as update:
                    modal.get_by_role('button', name='Update Flock', exact=True).click()
                self.assertEqual(update.value.status, 200, f'Flock update failed: {update.value.text()}')
                expect(modal).to_be_hidden()
                expect(row.get_by_role('cell').nth(3)).to_have_text(new_quantity)

                page.reload(wait_until='domcontentloaded')
                expect(page.get_by_role('heading', name='Current Flocks', exact=True)).to_be_visible()
                expect(row).to_have_count(1)
                expect(row.get_by_role('cell').nth(3)).to_have_text(new_quantity)
                print(f'Actual result: {flock_id} changed from {old_quantity} to {new_quantity} and persisted after reload.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
