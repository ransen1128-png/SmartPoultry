"""Verify that negative costs block creation of a bought flock."""

import os
import unittest


try:
    from tools.automation_browser import expect, expect_field_error, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, expect_field_error, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_058_negative_bought_flock_costs(self):
        """CASE-058 | Flock creation failed & invalid cost error shown."""
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

            scenarios = (
                ('negative purchase cost', '-1', '25', 'purchase_amount'),
                ('negative delivery fee', '100', '-1', 'delivery_cost'),
            )
            for scenario, purchase_amount, delivery_cost, invalid_field in scenarios:
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
                        ('purchase_amount', purchase_amount),
                        ('delivery_cost', delivery_cost),
                        ('purchase_date', '2025-01-01'),
                    ):
                        field = form.locator(f'[name="{name}"]')
                        field.fill(value)
                        expect(field).to_have_value(value)
                    invalid_cost = form.locator(f'[name="{invalid_field}"]')
                    self.assertTrue(invalid_cost.evaluate('field => field.validity.rangeUnderflow'))
                    message = invalid_cost.evaluate('field => field.validationMessage')
                    self.assertTrue(message)
                    modal.get_by_role('button', name='Save Flock', exact=True).click()

                    expect_field_error(invalid_cost)
                    expect(modal).to_be_visible()
                    print(f'{scenario}: {message}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
