"""Verify that valid farm details open branch management on the live site."""

import os
import unittest

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FARM_URL = f'{BASE_URL}/farm/branches/'


class LiveFarmTests(unittest.TestCase):
    def test_case_038_complete_farm_profile(self):
        """CASE-038 | Farm profile created successfully & farm information displayed with an Add Branch option."""
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

                page.goto(FARM_URL, timeout=90_000, wait_until='domcontentloaded')
                expect(page).to_have_url(FARM_URL)
                notification = page.locator('dialog#appDialog[open]')
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()

                if page.locator('#farmBranchesTitle').is_visible():
                    self.skipTest('Use a dedicated test account without a farm profile for this case.')
                submit = page.get_by_role('button', name='Create Farm Profile', exact=True)
                expect(submit).to_be_visible()
                form = page.locator('form').filter(has=submit)
                details = {
                    'farm_name': 'SMARTPOULTRY QA Farm',
                    'farm_address': 'Quezon City',
                    'established_date': '2025-01-01',
                    'contact_email': 'farm-test@example.invalid',
                    'contact_phone': '09123456789',
                }
                for name, value in details.items():
                    field = form.locator(f'[name="{name}"]')
                    field.fill(value)
                    expect(field).to_have_value(value)
                submit.click()

                expect(notification).to_be_visible()
                reminder = notification.filter(has_text='You need a farm profile before managing branches.')
                if reminder.is_visible():
                    reminder.get_by_role('button', name='Close notification').click()
                expect(notification.locator('#appDialogText')).to_contain_text(
                    'Farm profile created successfully. You can now add branches.',
                )
                notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()
                expect(page).to_have_url(FARM_URL)
                expect(submit).to_have_count(0)
                information = page.get_by_role('region', name='Farm Information', exact=True)
                expect(information).to_be_visible()
                for name in ('farm_name', 'farm_address', 'contact_email', 'contact_phone'):
                    expect(information.get_by_text(details[name], exact=True)).to_be_visible()
                expect(information.get_by_role('button', name='Add Branch', exact=True)).to_be_visible()
                print('Actual result: Farm profile created and farm information displayed with Add Branch.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
