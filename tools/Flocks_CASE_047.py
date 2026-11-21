"""Verify that empty required fields block updates to a live test flock."""

from getpass import getpass
import os
import unittest


from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
FLOCKS_URL = f'{BASE_URL}/flocks/'



class LiveFlockTests(unittest.TestCase):
    def test_case_047_empty_required_flock_edit_fields(self):
        """CASE-047 | Flock update failed & required field errors shown."""
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

                flock_id = os.environ.get('SMARTPOULTRY_TEST_FLOCK_ID') or 'QA-044-18e6c3e700'
                page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
                notification = page.locator('dialog#appDialog[open]')
                if notification.is_visible():
                    notification.get_by_role('button', name='Close notification').click()
                expect(notification).to_be_hidden()

                row = page.locator('#flocksBody tr').filter(
                    has=page.get_by_role('cell', name=flock_id, exact=True),
                )
                expect(row).to_be_visible()
                row.get_by_role('button', name='Edit', exact=True).click()
                modal = page.locator('#addFlockModal')
                expect(modal.get_by_role('heading', name='Edit Flock', exact=True)).to_be_visible()
                form = modal.locator('#addFlockForm')
                identifier = form.locator('[name="flock_id"]')
                quantity = form.locator('[name="quantity"]')
                saved_quantity = quantity.input_value()
                expect(identifier).to_have_value(flock_id)
                self.assertTrue(saved_quantity)
                for field in (identifier, quantity, form.locator('[name="correction_reason"]')):
                    field.fill('')
                    expect(field).to_have_value('')

                form.evaluate('''form => {
                    form.addEventListener('invalid', ({ target }) => {
                        if (target.validity.valueMissing) {
                            target.dataset.testValidationMessage = target.validationMessage;
                        }
                    }, true);
                }''')
                writes = []

                def track_update(request):
                    if request.url.startswith(f'{BASE_URL}/api/flocks/') and request.method in ('PATCH', 'PUT'):
                        writes.append(request)

                page.on('request', track_update)
                modal.get_by_role('button', name='Update Flock', exact=True).click()

                expect(notification.get_by_role('heading', name='Please Complete All Required Fields!')).to_be_visible()
                expect(notification.locator('#appDialogText')).to_have_text('Please fill out this field.')
                expect(modal).to_be_visible()
                for name in ('flock_id', 'quantity', 'correction_reason'):
                    field = form.locator(f'[name="{name}"]')
                    expect(field).to_have_attribute('data-test-validation-message', 'Please fill out this field.')
                self.assertFalse(writes, 'The browser sent a flock update request')

                page.reload(wait_until='domcontentloaded')
                row.get_by_role('button', name='Edit', exact=True).click()
                expect(identifier).to_have_value(flock_id)
                expect(quantity).to_have_value(saved_quantity)
                print(f'Actual result: Required fields were flagged. Flock {flock_id} still has quantity {saved_quantity}.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
