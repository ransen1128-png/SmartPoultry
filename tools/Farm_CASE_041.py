"""Verify that valid branch details create a branch on the live site."""

import os
import unittest
from uuid import uuid4


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FARM_URL = f'{BASE_URL}/farm/branches/'



class LiveFarmTests(unittest.TestCase):
    def test_case_041_valid_branch_details(self):
        """CASE-041 | Branch created successfully & displayed in the farm branch list."""
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

            page.goto(FARM_URL, timeout=90_000, wait_until='domcontentloaded')
            expect(page).to_have_url(FARM_URL)
            notification = page.locator('dialog#appDialog[open]')
            if notification.is_visible():
                notification.get_by_role('button', name='Close notification').click()
            expect(notification).to_be_hidden()

            branch_name = f'QA Branch 039 {uuid4().hex[:10]}'
            address = '123 QA Farm Road, Quezon City'
            phone = '09123456789'
            page.get_by_role('button', name='Add Branch', exact=True).click()
            modal = page.get_by_role('dialog', name='Add New Branch', exact=True)
            for label, value in (
                ('Branch Name', branch_name),
                ('Address', address),
                ('Contact Number', phone),
                ('Description (Optional)', 'Synthetic branch created by CASE-041.'),
            ):
                modal.get_by_label(label, exact=True).fill(value)
            modal.get_by_label('Status', exact=True).select_option('active')
            modal.get_by_role('button', name='Add Branch', exact=True).click()

            expect(notification.get_by_role('heading', name='Branch added successfully!', exact=True)).to_be_visible()
            expect(notification.locator('#appDialogText')).to_have_text('Your farm branch list has been updated.')
            notification.get_by_role('button', name='Close notification').click()
            expect(notification).to_be_hidden()
            expect(modal).to_be_hidden()
            row = page.locator('#branchList tr[data-branch-id]').filter(
                has=page.get_by_role('cell', name=branch_name, exact=True),
            )
            expect(row).to_be_visible()
            page.reload(wait_until='domcontentloaded')
            expect(row).to_be_visible()
            for value in (address, phone, 'Active'):
                expect(row.get_by_role('cell', name=value, exact=True)).to_be_visible()
            print(f'Actual result: {branch_name} was created and remains in the branch list after reload.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
