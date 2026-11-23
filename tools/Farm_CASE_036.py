"""Verify that empty required fields block live farm profile creation."""

import os
import unittest

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import expect_field_error, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect_field_error, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FARM_URL = f'{BASE_URL}/farm/branches/'
REQUIRED_FIELDS = ('farm_name', 'established_date', 'contact_email', 'contact_phone')


class LiveFarmTests(unittest.TestCase):
    def test_case_036_empty_required_fields(self):
        """CASE-036 | Farm profile creation failed & required field errors shown."""
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
                if page.locator('#farmBranchesTitle').is_visible():
                    self.skipTest('Use a dedicated test account without a farm profile for this case.')
                submit = page.get_by_role('button', name='Create Farm Profile', exact=True)
                form = page.locator('form').filter(has=submit)
                for name in REQUIRED_FIELDS:
                    expect(form.locator(f'[name="{name}"]')).to_have_value('')

                form.evaluate('''form => {
                    form.addEventListener('invalid', ({ target }) => {
                        if (target.validity.valueMissing) {
                            target.dataset.testValidationMessage = target.validationMessage;
                        }
                    }, true);
                }''')
                posts = []
                page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
                submit.click()

                expect(page).to_have_url(FARM_URL)
                self.assertEqual(posts, [], 'The browser submitted an incomplete farm profile')
                for name in REQUIRED_FIELDS:
                    with self.subTest(field=name):
                        field = form.locator(f'[name="{name}"]')
                        expect_field_error(field)
                        message = field.get_attribute('data-test-validation-message')
                        self.assertTrue(message, 'The browser did not report a required-field error')
                        print(f'{name}: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
