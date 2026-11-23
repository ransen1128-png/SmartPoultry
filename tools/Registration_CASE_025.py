"""Verify that empty required fields block registration on the live site."""

import unittest


try:
    from tools.automation_browser import expect, launch_browser, live_base_url
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url


REGISTER_URL = f'{live_base_url()}/register/'


class LiveRegistrationTests(unittest.TestCase):
    def test_case_025_empty_required_fields(self):
        """CASE-025 | Registration failed & required field errors shown."""
        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            page.goto(REGISTER_URL, timeout=90_000, wait_until='domcontentloaded')
            submit = page.get_by_role('button', name='Register', exact=True)
            form = page.locator('form').filter(has=submit)
            missing_fields = form.evaluate('''form => {
                const fields = [...form.elements].filter(field => field.willValidate && field.validity.valueMissing);
                form.addEventListener('invalid', ({ target }) => {
                    target.dataset.testValidationMessage = target.validationMessage;
                }, true);
                return fields.map(field => field.id);
            }''')
            self.assertTrue({'username', 'email', 'password', 'password2'}.issubset(missing_fields))

            posts = []
            page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
            submit.click()

            expect(page).to_have_url(REGISTER_URL)
            expect(page.locator(f'#{missing_fields[0]}')).to_be_focused()
            self.assertEqual(posts, [], 'The browser submitted the incomplete form')
            for field_id in missing_fields:
                with self.subTest(field=field_id):
                    message = page.locator(f'#{field_id}').get_attribute('data-test-validation-message')
                    self.assertTrue(message, 'The browser did not report a required-field error')
                    print(f'{field_id}: {message}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
