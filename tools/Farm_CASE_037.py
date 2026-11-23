"""Verify that invalid contact details block live farm profile creation."""

import os
import unittest


try:
    from tools.automation_browser import expect, expect_field_error, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, expect_field_error, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FARM_URL = f'{BASE_URL}/farm/branches/'



class LiveFarmTests(unittest.TestCase):
    def test_case_037_invalid_contact_details(self):
        """CASE-037 | Farm profile creation failed & validation error shown."""
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

            scenarios = (
                ('contact_email', 'invalid-email', 'typeMismatch'),
                ('contact_phone', '12345', 'patternMismatch'),
            )
            for field_name, invalid_value, validity_flag in scenarios:
                with self.subTest(field=field_name):
                    page.goto(FARM_URL, timeout=90_000, wait_until='domcontentloaded')
                    expect(page).to_have_url(FARM_URL)
                    notification = page.locator('dialog#appDialog[open]')
                    if notification.is_visible():
                        notification.get_by_role('button', name='Close notification').click()
                    expect(notification).to_be_hidden()

                    if page.locator('#farmBranchesTitle').is_visible():
                        self.skipTest('Use a dedicated test account without a farm profile for this case.')
                    submit = page.get_by_role('button', name='Create Farm Profile', exact=True)
                    form = page.locator('form').filter(has=submit)
                    values = {
                        'farm_name': 'Synthetic QA Farm',
                        'farm_address': 'QA Location',
                        'established_date': '2025-01-01',
                        'contact_email': 'farm-test@example.invalid',
                        'contact_phone': '09123456789',
                    }
                    del values[field_name]
                    for name, value in values.items():
                        form.locator(f'[name="{name}"]').fill(value)

                    field = form.locator(f'[name="{field_name}"]')
                    field.fill(invalid_value)
                    expect(field).to_have_value(invalid_value)
                    self.assertTrue(
                        field.evaluate('(field, flag) => field.validity[flag]', validity_flag),
                        f'Browser did not report {validity_flag} for {field_name}.',
                    )
                    message = field.evaluate('field => field.validationMessage')
                    self.assertTrue(message)

                    submit.click()
                    expect_field_error(field)
                    expect(submit).to_be_visible()
                    expect(page).to_have_url(FARM_URL)
                    print(f'{field_name}: {message}')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
