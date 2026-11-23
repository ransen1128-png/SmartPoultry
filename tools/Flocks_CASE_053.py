"""Verify that invalid quantity is rejected when editing a live test flock."""

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
    def test_case_053_invalid_flock_update(self):
        """CASE-053 | Flock update failed & validation error shown."""
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
                saved_quantity = quantity.input_value()
                self.assertTrue(saved_quantity)
                quantity.fill('-1')
                modal.get_by_label('Reason for correction', exact=True).fill('CASE-053 invalid quantity validation')
                modal.get_by_role('button', name='Update Flock', exact=True).click()

                error = modal.locator('[data-sp-inline-message], [data-sp-field-error]').filter(
                    has_text='Quantity cannot be negative.',
                ).first
                expect(error).to_contain_text('Quantity cannot be negative.')
                expect(error).to_be_visible()
                expect(modal).to_be_visible()
                page.reload(wait_until='domcontentloaded')
                row.get_by_role('button', name='Edit', exact=True).click()
                expect(quantity).to_have_value(saved_quantity)
                print(f'Actual result: Quantity cannot be negative. Saved quantity remains {saved_quantity}.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
