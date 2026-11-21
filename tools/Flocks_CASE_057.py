"""Verify that the flock details form shows the saved values."""

from getpass import getpass
import os
import unittest


from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_057_view_existing_flock_details(self):
        """CASE-057 | Flock details displayed successfully & correct information shown."""
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

                flock_id = os.environ.get('SMARTPOULTRY_TEST_FLOCK_ID') or 'QA-044-18e6c3e700'
                page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
                notification = page.locator('dialog#appDialog[open]')
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()

                row = page.locator('#flocksBody tr').filter(
                    has=page.get_by_role('cell', name=flock_id, exact=True),
                )
                expect(row).to_be_visible()
                with page.expect_response(
                    lambda response: response.url.startswith(f'{BASE_URL}/api/flocks/')
                    and response.url != f'{BASE_URL}/api/flocks/'
                    and response.request.method == 'GET',
                ) as detail:
                    row.get_by_role('button', name='Edit', exact=True).click()
                self.assertTrue(detail.value.ok, 'Could not load the saved flock')
                flock = detail.value.json()
                self.assertEqual(flock['flock_id'], flock_id)

                modal = page.locator('#addFlockModal')
                expect(modal.get_by_role('heading', name='Edit Flock', exact=True)).to_be_visible()
                for name in ('branch', 'flock_id', 'breed', 'quantity', 'status', 'acquisition_source'):
                    with self.subTest(field=name):
                        expect(modal.locator(f'[name="{name}"]')).to_have_value(str(flock[name]))
                expect(modal.locator('select[name="branch"] option:checked')).to_have_text(flock['branch_name'])
                print(f'Actual result: {flock_id} showed {flock["quantity"]} {flock["breed"]} in {flock["branch_name"]}.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
