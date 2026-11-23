"""Verify that an invalid purchase date blocks creation of a bought flock."""

import os
import unittest

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import expect_field_error, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect_field_error, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_059_invalid_bought_flock_purchase_date(self):
        """CASE-059 | Flock creation failed & invalid purchase date error shown."""
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
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()

                page.get_by_role('button', name='Add New Flock').click()
                modal = page.locator('#addFlockModal')
                form = modal.locator('#addFlockForm')
                branches = form.locator('select[name="branch"] option:not([value=""])')
                first_branch = branches.first.get_attribute('value')
                self.assertTrue(first_branch, 'An active branch is required for this test')
                form.locator('[name="branch"]').select_option(first_branch)
                form.locator('[name="breed"]').select_option('layers')
                form.locator('[name="acquisition_source"]').select_option('purchased')
                form.locator('[name="quantity"]').fill('10')
                form.locator('[name="purchase_amount"]').fill('100')
                form.locator('[name="delivery_cost"]').fill('25')
                date = form.get_by_label('Purchase date', exact=True)
                date.fill('2025-02-28')
                date.focus()
                # Move to the day segment and increment February 28 to February 29 in 2025.
                for key in ('ArrowRight', 'ArrowUp'):
                    date.press(key)
                submit = modal.get_by_role('button', name='Save Flock', exact=True)
                submit.focus()
                self.assertTrue(date.evaluate('field => field.validity.badInput'))
                message = date.evaluate('field => field.validationMessage')
                self.assertIn('invalid date', message.lower())

                writes = []

                def track_creation(request):
                    if request.url == f'{BASE_URL}/api/flocks/' and request.method == 'POST':
                        writes.append(request)

                page.on('request', track_creation)
                submit.click()
                expect_field_error(date)
                expect(modal).to_be_visible()
                self.assertFalse(writes, 'The browser sent a flock creation request')
                print(f'Actual result: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
