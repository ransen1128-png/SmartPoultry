"""Local login, password and feedback fixtures for integration tests."""

from django.contrib.auth import get_user_model

from tools.automation_browser import expect
from tools.feed_inventory_browser import FeedInventoryBrowserCase


class AccountIntegrationBrowserCase(FeedInventoryBrowserCase):
    original_password = 'Fixture!123'
    new_password = 'Integration!456'

    def login(self, user, password):
        self.page.goto(f'{self.live_server_url}/login/')
        self.page.get_by_label('Email', exact=True).fill(user.email)
        self.page.get_by_label('Password', exact=True).fill(password)
        self.page.get_by_role('button', name='Login', exact=True).click()

    def assert_password_replaced(self):
        self.page.driver.delete_all_cookies()
        self.login(self.user, self.original_password)
        expect(self.page.locator('#passwordError')).to_have_text('Incorrect email or password. Please try again.')
        self.login(self.user, self.new_password)
        expect(self.page).to_have_url(f'{self.live_server_url}/dashboard/')

    def staff_fixture(self):
        return get_user_model().objects.create_user(
            'integration-staff', 'integration-staff@example.invalid', self.original_password, is_staff=True,
        )
