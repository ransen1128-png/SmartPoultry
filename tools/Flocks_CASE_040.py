"""Verify that empty required fields block live flock creation."""

from getpass import getpass
import os
import unittest

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
FLOCKS_URL = f'{BASE_URL}/flocks/'
REQUIRED_FIELDS = ('branch', 'flock_id', 'breed', 'acquisition_source', 'quantity')


class LiveFlockTests(unittest.TestCase):
    def test_case_040_empty_required_flock_fields(self):
        """CASE-040 | Flock creation failed & required field errors shown."""
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

                page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
                expect(page).to_have_url(FLOCKS_URL)
                notification = page.locator('dialog#appDialog[open]')
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()
                page.get_by_role('button', name='Add New Flock').click()
                modal = page.locator('#addFlockModal')
                expect(modal).to_be_visible()
                submit = modal.get_by_role('button', name='Save Flock', exact=True)
                form = modal.locator('#addFlockForm')
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

                expect(page).to_have_url(FLOCKS_URL)
                expect(notification.get_by_role('heading', name='Please Complete All Required Fields!')).to_be_visible()
                expect(notification.get_by_text('Please select an item in the list.', exact=True)).to_be_visible()
                expect(modal).to_be_visible()
                self.assertEqual(posts, [], 'The browser submitted an incomplete flock form')
                for name in REQUIRED_FIELDS:
                    with self.subTest(field=name):
                        message = form.locator(f'[name="{name}"]').get_attribute('data-test-validation-message')
                        self.assertTrue(message, 'The browser did not report a required-field error')
                        print(f'{name}: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
