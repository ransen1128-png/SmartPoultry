"""Verify that valid flock details create a record in Current Flocks."""

import os
import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
    from tools.flock_rows import flock_row
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value
    from flock_rows import flock_row


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_051_valid_flock_details(self):
        """CASE-051 | Flock created successfully & displayed in the Current Flocks list."""
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

            if notification.is_visible():
                notification.get_by_role('button', name='Close notification').click()
            expect(notification).to_be_hidden()
            page.get_by_role('button', name='Add New Flock').click()
            branch = form.locator('select[name="branch"]')
            branch.select_option(index=1)
            branch_name = branch.locator('option:checked').inner_text()
            form.locator('[name="breed"]').select_option('layers')
            form.locator('[name="acquisition_source"]').select_option('own')
            form.locator('[name="quantity"]').fill('10')
            form.locator('[name="status"]').select_option('active')

            with page.expect_response(
                lambda response: response.url == f'{BASE_URL}/api/flocks/'
                and response.request.method == 'POST'
            ) as creation:
                modal.get_by_role('button', name='Save Flock', exact=True).click()
            self.assertEqual(creation.value.status, 201, 'The flock creation request failed')
            flock_id = creation.value.json()['flock_id']
            print(f'Created test flock: {flock_id}', flush=True)

            expect(modal).to_be_hidden()
            # Flock IDs are numbered per branch, so match the Branch and Flock ID columns exactly.
            expect(flock_row(page, flock_id, branch_name)).to_be_visible()
            page.reload(wait_until='domcontentloaded')
            expect(page.get_by_role('heading', name='Current Flocks', exact=True)).to_be_visible()
            row = flock_row(page, flock_id, branch_name)
            for value in (branch_name, 'layers', '10', 'active', 'Raised on my farm'):
                expect(row.get_by_role('cell', name=value, exact=True)).to_be_visible()
            print(f'Actual result: {flock_id} remains in Current Flocks after reload.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
