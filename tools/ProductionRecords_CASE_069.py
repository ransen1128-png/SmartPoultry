"""Verify that Production Records displays the empty stock and history states."""

import os
import unittest



try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
PRODUCTION_URL = f'{BASE_URL}/production-records/'



class LiveProductionRecordsTests(unittest.TestCase):
    def test_case_069_empty_production_records(self):
        """CASE-069 | No production stock available message shown & empty production history displayed."""
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

            page.goto(PRODUCTION_URL, timeout=90_000, wait_until='domcontentloaded')
            expect(page).to_have_url(PRODUCTION_URL)
            notification = page.locator('dialog#appDialog[open]')
            if notification.is_visible():
                notification.get_by_role('button', name='Close notification').click()
            expect(notification).to_be_hidden()

            expect(page.get_by_role('heading', name='Production Records', exact=True)).to_be_visible()
            expect(page.get_by_role('heading', name='No production stock available.', exact=True)).to_be_visible()

            history = page.locator('#productionHistoryPanel')
            page.get_by_role('button', name='History (0)', exact=True).click()
            expect(history.get_by_role('heading', name='Production History (0)', exact=True)).to_be_visible()
            table = history.locator('#productionHistoryTable')
            expect(table.get_by_text('No sold-out production batches.', exact=True)).to_be_visible()
            expect(table.locator('tbody tr[data-production-id]')).to_have_count(0)
            print('Actual result: No production stock available and no sold-out production batches.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
