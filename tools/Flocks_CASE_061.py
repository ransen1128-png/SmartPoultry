"""Verify that Flock History displays previously recorded flocks on Render."""

import os
import unittest



try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_061_view_flock_history(self):
        """CASE-061 | Flock history displayed successfully & previous flock records shown."""
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

            flock_id = read_test_value('SMARTPOULTRY_TEST_HISTORY_FLOCK_ID', 'Fixture flock ID: ')
            page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
            expect(page).to_have_url(FLOCKS_URL)
            notification = page.locator('dialog#appDialog[open]')
            if notification.is_visible():
                notification.get_by_role('button', name='Close notification').click()
            expect(notification).to_be_hidden()

            history = page.locator('#flockHistoryPanel')
            button = page.locator('#flockHistoryBtn')
            expect(history).to_be_hidden()
            button.click()
            expect(history.get_by_role('heading', name='Flock History', exact=True)).to_be_visible()
            record = history.locator('#flockHistoryBody tr').filter(
                has=page.get_by_role('cell', name=flock_id, exact=True),
            )
            expect(record).to_have_count(1)
            expect(record).to_be_visible()
            print(f'Actual result: Flock History opened and displayed saved flock {flock_id}.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
