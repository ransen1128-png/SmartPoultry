"""Shared fixtures for the Profile browser cases."""

from playwright.sync_api import expect

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class ProfileBrowserCase(FeedInventoryBrowserCase):
    def open_profile(self):
        self.page.locator('nav a[href="/profile/"]').filter(has_text='Profile').click()
        expect(self.page).to_have_url(f'{self.live_server_url}/profile/')
        expect(self.page.get_by_role('heading', name='Manage Profile', exact=True)).to_be_visible()
        self.profile_form = self.page.locator('main form').filter(
            has=self.page.get_by_role('button', name='Save Changes'),
        )

    def save_profile(self):
        self.profile_form.get_by_role('button', name='Save Changes').click()

    def assert_invalid_profile_field(self, label, value, validity_flag):
        self.open_profile()
        original = self.user.username, self.user.email
        field = self.profile_form.get_by_label(label, exact=True)
        field.fill(value)
        submissions = []

        def track_profile(request):
            if request.url == f'{self.live_server_url}/profile/' and request.method == 'POST':
                submissions.append(request)

        self.page.on('request', track_profile)
        self.save_profile()
        self.assertTrue(field.evaluate('(field, flag) => field.validity[flag]', validity_flag))
        message = field.evaluate('field => field.validationMessage')
        self.assertTrue(message)
        expect(self.page.get_by_text(message, exact=True)).to_be_visible()
        self.assertFalse(submissions, 'Invalid profile form was submitted')
        self.user.refresh_from_db()
        self.assertEqual((self.user.username, self.user.email), original)
        return message
