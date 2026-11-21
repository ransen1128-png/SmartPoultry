"""Profile browser test CASE-155."""

from playwright.sync_api import expect

from tools.profile_browser import ProfileBrowserCase


class ProfileCase155(ProfileBrowserCase):
    def test_case_155_profile(self):
        self.open_profile()
        for label in ('First Name', 'Last Name', 'Username', 'Email', 'Phone'):
            expect(self.profile_form.get_by_label(label, exact=True)).to_be_visible()
