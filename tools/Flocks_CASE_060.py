"""Verify that a bought flock creates a linked record in Expenses."""

from datetime import date
import os
import unittest

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_060_bought_flock_records_purchase_expense(self):
        """CASE-060 | Flock created successfully & purchase cost recorded in Expenses."""
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
                form.locator('[name="acquisition_source"]').select_option('purchased')
                form.locator('[name="quantity"]').fill('10')
                form.locator('[name="status"]').select_option('active')
                form.locator('[name="purchase_amount"]').fill('100')
                form.locator('[name="delivery_cost"]').fill('25')
                purchase_date = date.today().isoformat()
                form.locator('[name="purchase_date"]').fill(purchase_date)
                form.locator('[name="supplier"]').fill('Synthetic CASE-060 Supplier')

                with page.expect_response(
                    lambda response: response.url == f'{BASE_URL}/api/flocks/'
                    and response.request.method == 'POST'
                ) as creation:
                    modal.get_by_role('button', name='Save Flock', exact=True).click()
                response = creation.value
                self.assertEqual(response.status, 201, f'Flock creation failed: {response.text()}')
                flock = response.json()
                flock_id = flock['flock_id']
                row = page.locator('#flocksBody tr').filter(
                    has=page.get_by_role('cell', name=flock_id, exact=True),
                )
                print(f'Created test flock: {flock_id}', flush=True)

                expect(modal).to_be_hidden()
                expect(row).to_be_visible()
                expect(row.get_by_role('cell', name='Bought', exact=True)).to_be_visible()
                expense_id = flock['purchase_expense_id']
                self.assertIsNotNone(expense_id, 'The bought flock has no linked purchase expense')
                expense = page.request.get(f'{BASE_URL}/api/expenses/{expense_id}/')
                self.assertTrue(expense.ok, 'The linked purchase expense could not be loaded')
                record = expense.json()
                self.assertEqual(record['flock_purchase'], flock['id'])
                self.assertEqual(record['expense_type'], 'flock_purchase')
                self.assertEqual(record['date'], purchase_date)
                self.assertEqual(record['amount'], '125.00')

                page.goto(f'{BASE_URL}/expenses/', wait_until='domcontentloaded')
                expense_row = page.locator('#expensesBody tr').filter(
                    has=page.get_by_role('cell', name=f'Flock purchase: {flock_id}', exact=True),
                )
                expect(expense_row).to_have_count(1)
                expect(expense_row.get_by_role('cell', name=branch_name, exact=True)).to_be_visible()
                expect(expense_row.get_by_role('cell', name='\u20b1125.00', exact=True)).to_be_visible()
                print(f'Actual result: {flock_id} was created and linked to expense {expense_id} for 125.00.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
