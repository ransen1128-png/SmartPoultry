"""Verify that empty required fields block production record creation."""

from getpass import getpass
import os
import unittest


from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
PRODUCTION_URL = f'{BASE_URL}/production-records/'



class LiveProductionRecordsTests(unittest.TestCase):
    def test_case_059_empty_required_production_fields(self):
        """CASE-059 | Production record creation failed & required field errors shown."""
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

                page.goto(PRODUCTION_URL, timeout=90_000, wait_until='domcontentloaded')
                expect(page).to_have_url(PRODUCTION_URL)
                notification = page.locator('dialog#appDialog[open]')
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()

                page.get_by_role('link', name='Add Record').click()
                expect(page).to_have_url(f'{PRODUCTION_URL}add/')
                expect(page.get_by_role('heading', name='Add Production Record', exact=True)).to_be_visible()

                submit = page.get_by_role('button', name='Save Record')
                form = page.locator('form').filter(has=submit)
                required = form.evaluate('''form => {
                    const fields = [...form.elements].filter(field => field.willValidate && field.required);
                    for (const field of fields) {
                        if (field.value) field.value = '';
                    }
                    form.addEventListener('invalid', ({ target }) => {
                        if (target.validity.valueMissing) {
                            target.dataset.testValidationMessage = target.validationMessage;
                        }
                    }, true);
                    return fields.map(field => field.name);
                }''')
                self.assertTrue({'flock', 'quantity', 'date'}.issubset(required), required)

                requests = []

                def track_submission(request):
                    if request.url == f'{PRODUCTION_URL}add/' and request.method == 'POST':
                        requests.append(request)

                page.on('request', track_submission)
                submit.click()

                expect(notification.get_by_role('heading', name='Please Complete All Required Fields!')).to_be_visible()
                expect(page).to_have_url(f'{PRODUCTION_URL}add/')
                self.assertFalse(requests, 'The browser submitted the incomplete production record')
                for name in required:
                    with self.subTest(field=name):
                        field = form.locator(f'[name="{name}"]')
                        message = field.get_attribute('data-test-validation-message')
                        self.assertTrue(message, f'No required-field error for {name}')
                        print(f'{name}: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
