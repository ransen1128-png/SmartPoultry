"""Verify that saving one new flock assigns a unique numeric ID."""

from getpass import getpass
import os
import unittest


from playwright.sync_api import expect, sync_playwright


BASE_URL = os.environ.get('SMARTPOULTRY_TEST_BASE_URL', 'https://smartpoultry-l3qo.onrender.com').rstrip('/')
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_056_save_one_flock_with_automatic_id(self):
        """CASE-056 | Unique numeric Flock ID generated automatically & flock saved successfully."""
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

                page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
                expect(page).to_have_url(FLOCKS_URL)
                notification = page.locator('dialog#appDialog[open]')
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()

                api_url = f'{BASE_URL}/api/flocks/'
                next_url = api_url
                existing_ids = set()
                while next_url:
                    response = page.request.get(next_url)
                    self.assertTrue(response.ok, 'Could not load existing Flock IDs')
                    records = response.json()
                    existing_ids.update(record['flock_id'] for record in records['results'])
                    next_url = records['next']

                expected_id = next(
                    (f'{number:02d}' for number in range(1, 101)
                     if not {f'{number:02d}', str(number)} & existing_ids),
                    None,
                )
                self.assertIsNotNone(expected_id, 'The test account has no available numeric Flock IDs')

                page.get_by_role('button', name='Add New Flock').click()
                modal = page.locator('#addFlockModal')
                form = modal.locator('#addFlockForm')
                expect(form.get_by_label('Flock ID', exact=True)).to_have_value('')
                form.locator('[name="branch"]').select_option(index=1)
                form.locator('[name="breed"]').select_option('layers')
                form.locator('[name="acquisition_source"]').select_option('own')
                form.locator('[name="quantity"]').fill('10')

                with page.expect_response(
                    lambda response: response.url == api_url and response.request.method == 'POST',
                ) as creation:
                    modal.get_by_role('button', name='Save Flock', exact=True).click()
                response = creation.value
                self.assertEqual(response.status, 201, f'Flock creation failed: {response.text()}')
                flock_id = response.json()['flock_id']
                self.assertNotIn('flock_id', response.request.post_data_json)
                self.assertRegex(flock_id, r'^(?:0[1-9]|[1-9][0-9]|100)$')
                self.assertNotIn(flock_id, existing_ids)
                self.assertEqual(flock_id, expected_id)

                expect(modal).to_be_hidden()
                saved_flock = page.locator('#flocksBody').get_by_role('cell', name=flock_id, exact=True)
                expect(saved_flock).to_be_visible()
                page.reload(wait_until='domcontentloaded')
                expect(saved_flock).to_have_count(1)
                expect(saved_flock).to_be_visible()
                print(f'Actual result: Flock {flock_id} was assigned automatically and remained saved after reload.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
