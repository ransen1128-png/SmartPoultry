"""Verify that Flock History displays previously recorded flocks on Render."""

from getpass import getpass
import os
import unittest


from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_054_view_flock_history(self):
        """CASE-054 | Flock history displayed successfully & previous flock records shown."""
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

                flock_id = os.environ.get('SMARTPOULTRY_TEST_HISTORY_FLOCK_ID') or 'QA-043-e7ef8a3ea3'
                page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
                expect(page).to_have_url(FLOCKS_URL)
                notification = page.locator('dialog#appDialog[open]')
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()

                history = page.locator('#flockHistoryPanel')
                button = page.locator('#flockHistoryBtn')
                expect(history).to_be_hidden()
                expect(button).to_have_attribute('aria-expanded', 'false')
                button.click()
                expect(button).to_have_attribute('aria-expanded', 'true')
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
