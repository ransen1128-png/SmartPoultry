"""Verify that missing purchase details block creation of a bought flock."""

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
    def test_case_057_missing_bought_flock_purchase_details(self):
        """CASE-057 | Flock creation failed & required purchase field errors shown."""
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

                scenarios = (
                    ('missing purchase date and costs', '', 'Please fill out this field.'),
                    ('missing purchase costs', '2025-01-01', 'Enter the total chicken purchase cost or delivery fee.'),
                )
                for scenario, purchase_date, message in scenarios:
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
                        form.locator('[name="acquisition_source"]').select_option('purchased')
                        form.locator('[name="quantity"]').fill('10')
                        for name, value in (
                            ('purchase_amount', ''),
                            ('delivery_cost', ''),
                            ('purchase_date', purchase_date),
                        ):
                            field = form.locator(f'[name="{name}"]')
                            field.fill(value)
                            expect(field).to_have_value(value)
                        modal.get_by_role('button', name='Save Flock', exact=True).click()

                        if not purchase_date:
                            expect_field_error(form.locator('[name="purchase_date"]'))
                        else:
                            alert = modal.locator('[data-sp-inline-message], [data-sp-field-error]').filter(has_text=message)
                            expect(alert.first).to_be_visible()
                        expect(modal).to_be_visible()
                        print(f'{scenario}: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
