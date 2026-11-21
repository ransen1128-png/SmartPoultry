"""Verify that invalid or incomplete details block live flock creation."""

from getpass import getpass
import os
import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_041_invalid_or_incomplete_flock_details(self):
        """CASE-041 | Flock creation failed & validation error shown."""
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

                flock_id = f'QA-041-{uuid4().hex[:10]}'
                scenarios = (
                    ('negative quantity', flock_id, '-1', 'Quantity cannot be negative.'),
                    ('missing Flock ID', '', '10', 'Please fill out this field.'),
                )
                for scenario, identifier, quantity, message in scenarios:
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
                        form.locator('[name="flock_id"]').fill(identifier)
                        form.locator('[name="breed"]').select_option('layers')
                        form.locator('[name="acquisition_source"]').select_option('own')
                        form.locator('[name="quantity"]').fill(quantity)
                        expect(form.locator('[name="quantity"]')).to_have_value(quantity)
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
