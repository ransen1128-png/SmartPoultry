"""Run the successful admin login case against the deployed site."""

import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()


class LiveLoginTests(unittest.TestCase):
    def test_case_009_valid_admin_credentials_redirect_to_admin_dashboard(self):
        """CASE-009 | Valid admin credentials redirect to the Admin Dashboard."""
        email = read_test_value('SMARTPOULTRY_TEST_ADMIN_EMAIL', 'Admin test account email: ', secret=False)
        password = read_test_value('SMARTPOULTRY_TEST_ADMIN_PASSWORD', 'Admin test account password: ', secret=True)

        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            response = page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
            self.assertIsNotNone(response)
            self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

            page.get_by_label('Email', exact=True).fill(email)
            page.get_by_label('Password', exact=True).fill(password)
            page.get_by_role('button', name='Login', exact=True).click()

            expect(page).to_have_url(f'{BASE_URL}/admin-dashboard/', timeout=30_000)
            expect(page.get_by_role('heading', name='Users Management', exact=True)).to_be_visible()
            print('\nActual result: Admin login succeeded and the Admin Dashboard appeared.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
