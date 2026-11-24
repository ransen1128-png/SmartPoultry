"""Verify that saving one new flock assigns a unique numeric ID."""

import os
import unittest



try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_063_save_one_flock_with_automatic_id(self):
        """CASE-063 | Unique numeric Flock ID generated automatically & flock saved successfully."""
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

            page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
            expect(page).to_have_url(FLOCKS_URL)
            notification = page.locator('dialog#appDialog[open]')
            if notification.is_visible():
                notification.get_by_role('button', name='Close notification').click()
            expect(notification).to_be_hidden()

            api_url = f'{BASE_URL}/api/flocks/'
            page.get_by_role('button', name='Add New Flock').click()
            modal = page.locator('#addFlockModal')
            form = modal.locator('#addFlockForm')
            expect(form.get_by_label('Flock ID', exact=True)).to_have_value('')
            branch = form.locator('[name="branch"]')
            branch.select_option(index=1)
            branch_id = int(branch.input_value())
            branch_name = branch.locator('option:checked').inner_text()

            # Each branch numbers its own flocks from 01; numbers are never reissued.
            next_url = api_url
            existing_ids = set()
            while next_url:
                response = page.request.get(next_url)
                self.assertTrue(response.ok, 'Could not load existing Flock IDs')
                records = response.json()
                existing_ids.update(record['flock_id'] for record in records['results'] if record['branch'] == branch_id)
                next_url = records['next']
            highest = max((int(value) for value in existing_ids if value.isdigit()), default=0)
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
            self.assertRegex(flock_id, r'^\d{2,}$')
            self.assertNotIn(flock_id, existing_ids)
            self.assertGreater(int(flock_id), highest)

            expect(modal).to_be_hidden()
            saved_flock = page.locator('#flocksBody tr').filter(
                has=page.get_by_role('cell', name=flock_id, exact=True),
            ).filter(has=page.get_by_role('cell', name=branch_name, exact=True))
            expect(saved_flock).to_be_visible()
            page.reload(wait_until='domcontentloaded')
            expect(saved_flock).to_have_count(1)
            expect(saved_flock).to_be_visible()
            print(f'Actual result: Flock {flock_id} was assigned automatically and remained saved after reload.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
