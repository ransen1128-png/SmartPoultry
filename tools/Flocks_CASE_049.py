"""Verify that Flock IDs cannot be typed and that each new flock gets a unique ID in its branch."""

import os
import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'


class LiveFlockTests(unittest.TestCase):
    def test_case_049_duplicate_flock_id(self):
        """CASE-049 | Flock ID is read-only & each new flock receives a unique ID in its branch."""
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
            modal = page.locator('#addFlockModal')
            form = modal.locator('#addFlockForm')
            api_url = f'{BASE_URL}/api/flocks/'

            def branch_ids(branch_id):
                ids, next_url = set(), api_url
                while next_url:
                    response = page.request.get(next_url)
                    self.assertTrue(response.ok, 'Could not load existing Flock IDs')
                    records = response.json()
                    ids.update(r['flock_id'] for r in records['results'] if r['branch'] == branch_id)
                    next_url = records['next']
                return ids

            def submit_flock():
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()
                page.get_by_role('button', name='Add New Flock').click()
                branch = form.locator('select[name="branch"]')
                branch.select_option(index=1)
                if not before:  # IDs already used in this branch before the test adds flocks
                    before['branch'] = int(branch.input_value())
                    before['ids'] = branch_ids(before['branch'])
                identifier = form.locator('[name="flock_id"]')
                self.assertTrue(identifier.evaluate('field => field.readOnly'), 'The Flock ID field must be read-only.')
                expect(identifier).to_have_value('')
                form.locator('[name="breed"]').select_option('layers')
                form.locator('[name="acquisition_source"]').select_option('own')
                form.locator('[name="quantity"]').fill('10')
                with page.expect_response(
                    lambda response: response.url == api_url and response.request.method == 'POST',
                ) as creation:
                    modal.get_by_role('button', name='Save Flock', exact=True).click()
                self.assertEqual(creation.value.status, 201, f'Flock creation failed: {creation.value.text()}')
                expect(modal).to_be_hidden()
                return before['branch'], creation.value.json()['flock_id']

            before = {}

            branch_id, first_id = submit_flock()
            _, second_id = submit_flock()
            for value in (first_id, second_id):
                self.assertRegex(value, r'^\d{2,}$')
                self.assertNotIn(value, before['ids'])
            self.assertNotEqual(first_id, second_id, 'Two new flocks in one branch received the same Flock ID.')
            print(f'Actual result: The Flock ID field is read-only; new flocks received {first_id} and {second_id} '
                  f'in branch {branch_id}, neither used before.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
