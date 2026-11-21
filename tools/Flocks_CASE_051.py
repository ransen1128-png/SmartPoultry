"""Verify that negative costs block creation of a bought flock."""

from getpass import getpass
import os
import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_051_negative_bought_flock_costs(self):
        """CASE-051 | Flock creation failed & invalid cost error shown."""
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

                flock_id = f'QA-051-{uuid4().hex[:10]}'
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
                        form.locator('[name="flock_id"]').fill(flock_id)
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

                        expect(notification).to_be_visible()
                        expect(notification.locator('#appDialogText')).to_contain_text(message)
                        expect(modal).to_be_visible()
                        expect(page.get_by_role('cell', name=flock_id, exact=True)).to_have_count(0)
                        print(f'{scenario}: {notification.locator("#appDialogText").inner_text()}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
