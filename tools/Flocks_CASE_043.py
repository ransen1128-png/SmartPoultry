"""Verify that negative and zero quantities block live flock creation."""

from getpass import getpass
import os
import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_043_nonpositive_flock_quantity(self):
        """CASE-043 | Flock creation failed & invalid quantity error shown."""
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


                scenarios = (
                    ('negative quantity', '-1'),
                    ('zero quantity', '0'),
                )
                for scenario, quantity in scenarios:
                    with self.subTest(scenario=scenario):
                        flock_id = f'QA-043-{uuid4().hex[:10]}'
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
                        form.locator('[name="acquisition_source"]').select_option('own')
                        form.locator('[name="quantity"]').fill(quantity)
                        expect(form.locator('[name="quantity"]')).to_have_value(quantity)
                        creation_responses = []

                        def track_creation(response):
                            if response.url == f'{BASE_URL}/api/flocks/' and response.request.method == 'POST':
                                creation_responses.append(response)

                        page.on('response', track_creation)
                        try:
                            modal.get_by_role('button', name='Save Flock', exact=True).click()
                            expect(notification).to_be_visible()
                        finally:
                            page.remove_listener('response', track_creation)

                        for response in creation_responses:
                            self.assertFalse(
                                response.ok,
                                f'Render accepted quantity {quantity} and created test flock {flock_id}.',
                            )
                        message = notification.locator('#appDialogText')
                        expect(message).to_contain_text('quantity', ignore_case=True)
                        expect(modal).to_be_visible()
                        expect(page.get_by_role('cell', name=flock_id, exact=True)).to_have_count(0)
                        print(f'{scenario}: {message.inner_text()}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
