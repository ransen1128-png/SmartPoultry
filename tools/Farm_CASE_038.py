"""Verify that invalid or incomplete details block live branch creation."""

from getpass import getpass
import os
import unittest
from contextlib import contextmanager

from playwright.sync_api import expect, sync_playwright


BASE_URL = 'https://smartpoultry-l3qo.onrender.com'
FARM_URL = f'{BASE_URL}/farm/branches/'



@contextmanager
def observe_posts(page):
    posts = []

    def track(request):
        if request.method == 'POST':
            posts.append(request.url)

    page.on('request', track)
    try:
        yield posts
    finally:
        page.remove_listener('request', track)


class LiveFarmTests(unittest.TestCase):
    def test_case_038_invalid_or_incomplete_branch_details(self):
        """CASE-038 | Branch creation failed & validation error shown."""
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

                scenarios = (
                    ('invalid contact number', 'QA Branch Address', '12345', 'contact_number', 'patternMismatch'),
                    ('missing address', '', '09123456789', 'address', 'valueMissing'),
                )
                for scenario, address, phone, field_name, flag in scenarios:
                    with self.subTest(scenario=scenario):
                        page.goto(FARM_URL, timeout=90_000, wait_until='domcontentloaded')
                        notification = page.locator('dialog#appDialog[open]')
                        if notification.is_visible():
                            notification.get_by_role('button', name='Close notification').click()
                        expect(notification).to_be_hidden()

                        page.get_by_role('button', name='Add Branch', exact=True).click()
                        modal = page.get_by_role('dialog', name='Add New Branch', exact=True)
                        form = modal.locator('#addBranchForm')
                        for name, value in (
                            ('branch_name', 'Synthetic QA Branch'),
                            ('address', address),
                            ('contact_number', phone),
                        ):
                            field = form.locator(f'[name="{name}"]')
                            field.fill(value)
                            expect(field).to_have_value(value)
                        form.locator('[name="status"]').select_option('active')

                        field = form.locator(f'[name="{field_name}"]')
                        self.assertTrue(field.evaluate('(input, flag) => input.validity[flag]', flag))
                        message = field.evaluate('input => input.validationMessage')
                        self.assertTrue(message)
                        with observe_posts(page) as posts:
                            modal.get_by_role('button', name='Add Branch', exact=True).click()
                            expect(notification).to_be_visible()
                            expect(notification.locator('#appDialogText')).to_have_text(message)
                            expect(modal).to_be_visible()
                            expect(page).to_have_url(FARM_URL)
                        self.assertEqual(posts, [], 'The browser sent a branch creation request')
                        print(f'{scenario}: {message}')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
