"""Verify that invalid or incomplete details block live flock creation."""

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
    def test_case_048_invalid_or_incomplete_flock_details(self):
        """CASE-048 | Flock creation failed & validation error shown."""
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

                scenarios = (('negative quantity', '-1'), ('missing quantity', ''))
                for scenario, quantity in scenarios:
                    with self.subTest(scenario=scenario):
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
                        form.locator('[name="acquisition_source"]').select_option('own')
                        form.locator('[name="quantity"]').fill(quantity)
                        expect(form.locator('[name="quantity"]')).to_have_value(quantity)
                        modal.get_by_role('button', name='Save Flock', exact=True).click()

                        if quantity:
                            alert = modal.locator('[data-sp-inline-message], [data-sp-field-error]')
                            expect(alert.filter(has_text='Quantity cannot be negative.').first).to_be_visible()
                        else:
                            expect_field_error(form.locator('[name="quantity"]'))
                        expect(modal).to_be_visible()
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
