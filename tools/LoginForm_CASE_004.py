"""Run the successful login case against the deployed site."""

import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()


class LiveLoginTests(unittest.TestCase):
    def test_case_004_valid_credentials_redirect_to_dashboard(self):
        """CASE-004 | Valid credentials redirect to the Dashboard."""
        email = read_test_value('SMARTPOULTRY_TEST_EMAIL', 'Registered email for userx: ', secret=False)
        password = read_test_value('SMARTPOULTRY_TEST_PASSWORD', 'Password for userx: ', secret=True)

        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            response = page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
            self.assertIsNotNone(response)
            self.assertTrue(response.ok, f'Login page returned HTTP {response.status}')

            page.get_by_label('Email', exact=True).fill(email)
            page.get_by_label('Password', exact=True).fill(password)
            page.get_by_role('button', name='Login', exact=True).click()

            expect(page).to_have_url(f'{BASE_URL}/dashboard/', timeout=30_000)
            expect(page.get_by_role('heading', name='Dashboard', exact=True)).to_be_visible()
            print('\nActual result: Login succeeded and the Dashboard appeared.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
